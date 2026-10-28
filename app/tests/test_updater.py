import base64,hashlib,io,json,os,plistlib,stat,subprocess,sys,tempfile,threading,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import updater as U

class Response(io.BytesIO):
 def __init__(self,body,declared=None):super().__init__(body);self.headers={'Content-Length':str(len(body) if declared is None else declared)}
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

class UpdaterTests(unittest.TestCase):
 def archive(self,root,version='1.5.0',extra=None):
  p=root/'update.zip'
  with zipfile.ZipFile(p,'w') as z:
   z.writestr('Wrapper/ช่วยด้วยจ้า.app/Contents/Info.plist',plistlib.dumps({'CFBundleIdentifier':U.BUNDLE_ID,'CFBundleShortVersionString':version,'CFBundleExecutable':'studio'}))
   exe=zipfile.ZipInfo('Wrapper/ช่วยด้วยจ้า.app/Contents/MacOS/studio');exe.external_attr=(stat.S_IFREG|0o755)<<16;z.writestr(exe,b'#!/bin/sh\nexit 0\n')
   if extra:z.writestr(extra,b'bad')
  return p
 def test_cleanup_only_older_owned_backups(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);app=root/'Studio.app';trash=root/'trash'
   for name,bundle,version in [('Studio.backup-old.app',U.BUNDLE_ID,'1.5.1'),('Studio.backup-other.app','other','1.0'),('Studio.backup-new.app',U.BUNDLE_ID,'99.0')]:
    p=root/name/'Contents';p.mkdir(parents=True);(p/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':bundle,'CFBundleShortVersionString':version}))
   with patch.object(U,'CURRENT_VERSION','1.5.8'):
    moved=U.cleanup_legacy_backups(app,trash)
   self.assertEqual(len(moved),1);self.assertFalse((root/'Studio.backup-old.app').exists());self.assertTrue((root/'Studio.backup-other.app').exists());self.assertTrue((root/'Studio.backup-new.app').exists())
 def test_version_padding_and_bad_version(self):
  self.assertEqual(U._parse_version('v1.4'),U._parse_version('1.4.0'))
  self.assertGreater(U._parse_version('1.5'),U._parse_version('1.4.99'))
  with self.assertRaises(ValueError):U._parse_version('latest')
 def test_manifest_requires_real_release_and_hash(self):
  metadata={'version':'9.0','download_url':'https://github.com/utccedit1/SPKKB/releases/download/v9.0/SPKKB.app.zip','sha256':'a'*64,'size':123}
  with patch.object(U.urllib.request,'urlopen',side_effect=lambda *a,**k:Response(json.dumps({'content':base64.b64encode(json.dumps(metadata).encode()).decode()}).encode())):self.assertTrue(U.check_for_update()['available'])
  metadata['sha256']=''
  with patch.object(U.urllib.request,'urlopen',side_effect=lambda *a,**k:Response(json.dumps({'content':base64.b64encode(json.dumps(metadata).encode()).decode()}).encode())):self.assertIn('error',U.check_for_update())
 def test_download_checks_hash_length_and_zip(self):
  with tempfile.TemporaryDirectory() as folder:
   payload=self.archive(Path(folder)).read_bytes();digest=hashlib.sha256(payload).hexdigest()
   with patch.object(U.urllib.request,'urlopen',side_effect=lambda *a,**k:Response(payload)):
    path=U.download_update('https://example.invalid/update',expected_sha256=digest,expected_size=len(payload));self.assertEqual(path.read_bytes(),payload)
    import shutil;shutil.rmtree(path.parent)
    with self.assertRaises(ValueError):U.download_update('https://example.invalid/update',expected_sha256='b'*64,expected_size=len(payload))
   with patch.object(U.urllib.request,'urlopen',return_value=Response(payload,declared=len(payload)+1)):
    with self.assertRaises(ValueError):U.download_update('https://example.invalid/update')
 def test_nested_app_permissions_and_version(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(U.sys,'platform','linux'):
   p=self.archive(Path(folder));app=U.extract_app(p,'1.5.0');self.assertTrue(os.access(app/'Contents/MacOS/studio',os.X_OK))
  with tempfile.TemporaryDirectory() as folder,patch.object(U.sys,'platform','linux'):
   with self.assertRaises(ValueError):U.extract_app(self.archive(Path(folder),'1.4'),'1.5.0')
 def test_zip_traversal_and_external_symlinks_are_rejected(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(U.sys,'platform','linux'):
   with self.assertRaises(ValueError):U.extract_app(self.archive(Path(folder),extra='../outside'))
  with tempfile.TemporaryDirectory() as folder,patch.object(U.sys,'platform','linux'):
   p=self.archive(Path(folder))
   with zipfile.ZipFile(p,'a') as z:
    entry=zipfile.ZipInfo('Wrapper/ช่วยด้วยจ้า.app/link');entry.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(entry,'../../../outside')
   with self.assertRaises(ValueError):U.extract_app(p)
 def test_dev_mode_does_not_report_fake_success(self):
  with patch.object(U,'_get_app_bundle_path',return_value=None):
   with self.assertRaises(ValueError):U.apply_update(Path('/unused.zip'))
   manager=U.UpdateManager();manager.state='update_available';self.assertFalse(manager.download_and_apply_async());self.assertEqual(manager.state,'error')
 def test_manager_prevents_double_install_and_keeps_errors(self):
  entered=threading.Event();release=threading.Event();manager=U.UpdateManager();manager.state='update_available';manager.info={'download_url':'x','sha256':'a'*64,'size':1,'latest_version':'9'}
  def fail(*args):entered.set();release.wait(2);raise ValueError('checksum mismatch')
  with patch.object(U,'_get_app_bundle_path',return_value=Path('/App.app')),patch.object(U,'download_update',side_effect=fail):
   self.assertTrue(manager.download_and_apply_async());self.assertTrue(entered.wait(1));self.assertFalse(manager.download_and_apply_async());self.assertFalse(manager.check_async());release.set()
   for t in threading.enumerate():
    if t.name=='update-install':t.join(2)
  self.assertEqual(manager.state,'error');self.assertIn('checksum',manager.error)
 def test_active_editing_job_blocks_install(self):
  from ks import event_jobs as J
  manager=U.UpdateManager();manager.state='update_available'
  with J._lock:J._jobs['updater-active-test']={'state':'running'}
  try:
   self.assertFalse(manager.download_and_apply_async());self.assertEqual(manager.state,'update_available');self.assertIn('กำลังทำอยู่',manager.error)
  finally:
   with J._lock:J._jobs.pop('updater-active-test',None)
 def test_github_rate_limit_falls_back_to_raw_manifest(self):
  import urllib.error
  metadata={'version':'9.0','download_url':'https://github.com/utccedit1/SPKKB/releases/download/v9.0/SPKKB.app.zip','sha256':'a'*64,'size':123}
  with patch.object(U.urllib.request,'urlopen',side_effect=[urllib.error.HTTPError('https://api.github.com',403,'limited',{},None),Response(json.dumps(metadata).encode())]):
   self.assertTrue(U.check_for_update()['available'])
 def helper(self,fail_open=False):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);app=root/"ชื่อ มีช่องว่าง ' $.app";stage=root/'staged.app';backup=root/'backup.app';app.mkdir();stage.mkdir();(app/'version').write_text('old');(stage/'version').write_text('new');receipt=root/'receipt.json'
  script=U._helper_text(app,stage,backup,receipt,99999999,root/'log',trash_dir=root/'trash');script=script.replace('/usr/bin/open','/usr/bin/false' if fail_open else '/usr/bin/true');path=root/'install.sh';path.write_text(script);result=subprocess.run(['/bin/sh',str(path)],capture_output=True)
  return app,stage,backup,json.loads(receipt.read_text()),result
 def test_helper_installs_and_preserves_previous_app(self):
  app,stage,backup,receipt,result=self.helper();self.assertEqual(result.returncode,0);self.assertEqual((app/'version').read_text(),'new');self.assertEqual((Path(receipt['backup'])/'version').read_text(),'old');self.assertFalse(backup.exists());self.assertEqual(receipt['state'],'installed')
 def test_helper_restores_previous_app_if_relaunch_fails(self):
  app,stage,backup,receipt,result=self.helper(True);self.assertNotEqual(result.returncode,0);self.assertEqual((app/'version').read_text(),'old');self.assertEqual(receipt['state'],'error')
 def test_installer_exits_application_not_just_worker(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);app=root/'app.app';app.mkdir();staged=root/'new.app';staged.mkdir();timer=unittest.mock.MagicMock()
   with patch.object(U,'_installation_target',return_value=app),patch.object(U,'_get_app_bundle_path',return_value=app),patch.object(U,'extract_app',return_value=staged),patch.object(U,'STATE_DIR',root),patch.object(U,'RECEIPT',root/'receipt.json'),patch.object(U.subprocess,'run'),patch.object(U.subprocess,'Popen'),patch.object(U.threading,'Timer',return_value=timer) as make_timer,patch.object(U.os,'_exit') as exit_process:
    self.assertTrue(U.apply_update(root/'update.zip','1.5.0'));make_timer.call_args.args[1]();exit_process.assert_called_once_with(0);timer.start.assert_called_once()

class RelocationTests(unittest.TestCase):
 def test_readonly_mount_uses_user_applications(self):
  with tempfile.TemporaryDirectory() as d,patch.object(U.Path,'home',return_value=Path(d)):
   target=U._installation_target(Path('/Volumes/Installer/ช่วยด้วยจ้า.app'))
   self.assertEqual(target,Path(d)/'Applications/ช่วยด้วยจ้า.app')
 def test_translocated_app_uses_user_applications(self):
  with tempfile.TemporaryDirectory() as d,patch.object(U.Path,'home',return_value=Path(d)):
   self.assertEqual(U._installation_target(Path('/private/var/folders/temp/AppTranslocation/id/d/ช่วยด้วยจ้า.app')),Path(d)/'Applications/ช่วยด้วยจ้า.app')
 def test_existing_system_install_keeps_same_path(self):
  with tempfile.TemporaryDirectory() as d,patch.object(U.Path,'home',return_value=Path(d)),patch.object(U,'_probe_install_directory',return_value=True):
   self.assertEqual(U._installation_target(Path('/Applications/ช่วยด้วยจ้า.app')),Path('/Applications/ช่วยด้วยจ้า.app'))
 def test_writable_build_location_uses_one_canonical_installation(self):
  with tempfile.TemporaryDirectory() as d,patch.object(U.Path,'home',return_value=Path(d)):
   app=Path(d)/'build/Studio.app';app.mkdir(parents=True);self.assertEqual(U._installation_target(app),Path(d)/'Applications/ช่วยด้วยจ้า.app')
 def test_no_writable_destination_reports_error(self):
  with patch.object(U,'_probe_install_directory',return_value=False):
   with self.assertRaisesRegex(ValueError,'Applications'):U._installation_target(Path('/Applications/Studio.app'))
 def test_unrelated_app_not_overwritten(self):
  with tempfile.TemporaryDirectory() as d,patch.object(U.Path,'home',return_value=Path(d)):
   target=Path(d)/'Applications/ช่วยด้วยจ้า.app/Contents';target.mkdir(parents=True)
   (target/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'another.app'}))
   with self.assertRaisesRegex(ValueError,'ไม่เขียนทับ'):U._installation_target(Path('/Volumes/Test/Studio.app'))
 def run_relocation(self,fail=False):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
  source=root/'old.app';stage=root/'stage.app';target=root/'installed.app';backup=root/'backup.app'
  for folder in (source,stage,backup):folder.mkdir()
  (source/'version').write_text('old');(stage/'version').write_text('new');(backup/'version').write_text('old')
  receipt=root/'receipt';script=U._helper_text(target,stage,backup,receipt,99999999,root/'log',source,trash_dir=root/'trash')
  script=script.replace('/usr/bin/open','/usr/bin/false' if fail else '/usr/bin/true')
  path=root/'install.sh';path.write_text(script);result=subprocess.run(['/bin/sh',str(path)],capture_output=True)
  return source,target,backup,json.loads(receipt.read_text()),result
 def test_relocation_installs_without_changing_source(self):
  source,target,backup,receipt,result=self.run_relocation()
  self.assertEqual(result.returncode,0);self.assertFalse(source.exists());self.assertEqual((target/'version').read_text(),'new');self.assertFalse(backup.exists());self.assertEqual((Path(receipt['backup'])/'version').read_text(),'old');self.assertEqual(receipt['installed_app'],str(target))
 def test_relocation_failure_preserves_original(self):
  source,target,backup,receipt,result=self.run_relocation(True)
  self.assertNotEqual(result.returncode,0);self.assertFalse(target.exists());self.assertEqual((source/'version').read_text(),'old');self.assertEqual((backup/'version').read_text(),'old');self.assertEqual(receipt['state'],'error')
 def test_stage_failure_does_not_quit_application(self):
  with tempfile.TemporaryDirectory() as d:
   app=Path(d)/'current.app';app.mkdir()
   with patch.object(U,'_installation_target',return_value=app),patch.object(U,'_get_app_bundle_path',return_value=app),patch.object(U,'extract_app',return_value=Path(d)/'new.app'),patch.object(U.subprocess,'run',side_effect=OSError('disk full')),patch.object(U.threading,'Timer') as timer:
    with self.assertRaises(OSError):U.apply_update(Path(d)/'zip','1.5.3')
    timer.assert_not_called();self.assertTrue(app.exists())

if __name__=='__main__':unittest.main()
