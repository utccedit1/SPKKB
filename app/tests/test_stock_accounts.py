import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ks import stock_accounts as A,stock_browser as B,stock_media as M


class StockTests(unittest.TestCase):
    def test_users_and_services_have_separate_private_roots(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(A,'private_root',return_value=Path(folder)/'stock_private'):
            one=A.user_root('person-one');two=A.user_root('person-two')
            self.assertNotEqual(one,two);self.assertNotIn('person-one',str(one));self.assertEqual(one.stat().st_mode&0o777,0o700)
            self.assertNotEqual(one/'artlist',one/'envato')

    def test_jobs_cannot_be_read_by_another_user(self):
        with patch.dict(A._jobs,{'fixture':dict(owner='one',state='done',message='finished')},clear=True):
            with self.assertRaises(ValueError):A.status('two','fixture')
            self.assertNotIn('owner',A.status('one','fixture'))

    def test_public_status_contains_no_browser_secrets(self):
        with patch.object(A,'runtime',return_value=True),patch.dict(A._peers,{},clear=True):
            value=json.dumps(A.public_status('one'))
            for forbidden in ('cookie','password','token','browser-profile','client_secret'):self.assertNotIn(forbidden,value)
        with self.assertRaises(ValueError):A.handle('one',{'action':'download','provider':'artlist','password':'ignored'})

    def test_only_real_provider_item_links_can_be_used(self):
        good='https://artlist.io/stock-footage/clip/students-campus/123'
        for bad in ('http://artlist.io/stock-footage/clip/test/123','https://artlist.io.evil.test/stock-footage/clip/test/123',good+'?token=secret','file:///tmp/a.mp4','https://artlist.io/ai/video-generator'):
            self.assertFalse(B.safe_item(bad,'broll'))
        selected=B.rank_items([dict(href=good,title='Students on Campus'),dict(href='/stock-footage/clip/ocean/234',title='Blue Ocean')],'university students campus','broll')
        self.assertEqual(len(selected),1);self.assertEqual(selected[0]['url'],good)

    def test_media_verification_rejects_preview_html_and_too_large(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'preview.mp4';p.write_bytes(b'x'*2048)
            with self.assertRaises(B.StockError):B.verify_file(p,'broll')
            p=Path(folder)/'download.html';p.write_bytes(b'x'*2048)
            with self.assertRaises(B.StockError):B.verify_file(p,'broll')
            p=Path(folder)/'clip.mp4';p.write_bytes(b'x'*2048)
            with patch.object(B,'_duration',return_value=0),self.assertRaises(B.StockError):B.verify_file(p,'broll')
            with patch.object(B,'_duration',return_value=5):self.assertEqual(B.verify_file(p,'broll')['duration'],5)

    def test_stock_requests_must_reference_selected_captions(self):
        captions=[dict(start=i*5,end=(i+1)*5,text='speech') for i in range(6)]
        story=dict(duration=20,cuts=[dict(first_id=0,last_id=1,start=0,end=10),dict(first_id=4,last_id=5,start=20,end=30)])
        raw=dict(stock_requests=[dict(kind='broll',query='university students',first_id=4),dict(kind='music',query='calm instrumental')])
        rows=M.requests(raw,story,captions,True);self.assertEqual(rows[0]['start'],10)
        self.assertEqual(M.requests(raw,story,captions,False),[])
        bad=copy.deepcopy(raw);bad['stock_requests'][0]['first_id']=3
        with self.assertRaises(ValueError):M.requests(bad,story,captions,True)
        bad=copy.deepcopy(raw);bad['stock_requests'][0]['query']='https://bad.test'
        with self.assertRaises(ValueError):M.requests(bad,story,captions,True)

    def test_login_requires_positive_account_signal(self):
        from unittest.mock import MagicMock
        page=MagicMock();page.url='https://artlist.io/stock-footage';page.locator.return_value.inner_text.return_value='Stock footage'
        page.get_by_role.return_value.count.return_value=0
        with self.assertRaises(B.StockError):B.ensure_session(page,'artlist')
        page.url='https://accounts.example.test/'
        with self.assertRaises(B.StockError):B.ensure_session(page,'artlist')

    def test_generated_ui_has_no_credential_entry(self):
        from ks.stock_accounts_ui import UI
        self.assertNotIn('type="password"',UI);self.assertNotIn('localStorage',UI)
        self.assertIn('ตรวจบัญชีหลังล็อกอิน',UI)


class StockTimelineTests(unittest.TestCase):
    def test_footage_covers_canvas_in_both_orientations(self):
        for width,height,cw,ch,scale in [(1920,1080,1080,1920,256/81),(1080,1920,1920,1080,256/81),(1080,1920,1080,1920,1)]:
            draft={'canvas_config':dict(width=cw,height=ch),'materials':{'videos':[dict(id='stock',width=width,height=height)]}}
            segment={'material_id':'stock','clip':{'transform':{'x':0,'y':0}}}
            self.assertAlmostEqual(M.fill_frame(draft,segment),scale)
            self.assertAlmostEqual(segment['clip']['scale']['x'],scale)
            self.assertEqual(segment['clip']['transform'],{'x':0,'y':0})
        with self.assertRaises(ValueError):M.fill_frame({}, {'material_id':'missing'})

    def test_downloaded_assets_are_imported_muted_and_published_without_account_data(self):
        import subprocess,wave
        from ks import cli_lab as L,cli_lab_story as S,core_engine as CE,cli_lab_commit as C
        ffmpeg=CE.ac_ffmpeg_bin()
        if not ffmpeg:self.skipTest('ffmpeg optional')
        try:L.executable()
        except ValueError:self.skipTest('CLI optional')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);video=root/'clip.mp4';music=root/'music.wav';work=root/'work';work.mkdir()
            subprocess.run([ffmpeg,'-nostdin','-y','-v','error','-f','lavfi','-i','color=c=blue:s=64x64:r=30','-t','3','-c:v','libx264',str(video)],check=True,timeout=20)
            with wave.open(str(music),'wb') as f:f.setparams((1,2,16000,0,'NONE','not compressed'));f.writeframes(__import__('array').array('h',[round(4000*__import__('math').sin(2*__import__('math').pi*440*i/16000)) for i in range(160000)]).tobytes())
            draft={'id':'source','duration':12000000,'fps':30,'canvas_config':{'width':1080,'height':1920},'materials':{'videos':[],'audios':[],'texts':[]},'tracks':[]}
            (work/'draft_info.json').write_text(json.dumps(draft))
            records={'broll':dict(path=str(video),provider='artlist',url='https://artlist.io/stock-footage/clip/office/1',title='Office',duration=3,sha256='fixture-video',license_status='downloaded_via_own_account'),'music':dict(path=str(music),provider='artlist',url='https://artlist.io/royalty-free-music/song/calm/2',title='Calm',duration=10,sha256='fixture-audio',license_status='downloaded_via_own_account')}
            plan=dict(stock_destination=str(root/'project-stock'),auto_stock=True,stock_provider='artlist',stock_requests=[dict(kind='broll',query='office workers',start=4),dict(kind='music',query='calm instrumental',start=0)])
            owners=[]
            def receive(owner,provider,request,progress):owners.append(owner);return records[request['kind']]
            with patch.object(A,'wait_download',side_effect=receive):M.apply(work,plan,'fixture-owner',L.run_cli,lambda m:None)
            result=json.loads((work/'draft_info.json').read_bytes());C.validate(result)
            self.assertEqual(result['duration'],12000000)
            self.assertEqual(next(t for t in result['tracks'] if t['type']=='video')['segments'][0]['volume'],0)
            self.assertEqual(next(t for t in result['tracks'] if t['type']=='audio')['segments'][0]['volume'],1)
            self.assertEqual(owners,['fixture-owner','fixture-owner'])
            destination=S.publish(work,result,root/'outputs',plan)
            audit=(destination/'stock_report.json').read_text()
            self.assertTrue(list((root/'project-stock/B-roll').glob('*.mp4')))
            self.assertTrue(list((root/'project-stock/Music').glob('*.wav')))
            self.assertTrue(list((root/'project-stock/B-roll').glob('*.stock.json')))
            self.assertNotIn('fixture-owner',audit);self.assertNotIn('browser-profile',audit)
            for kind in ('videos','audios'):
                material=json.loads((destination/'draft_info.json').read_bytes())['materials'][kind][0]
                self.assertTrue(Path(material['path']).is_file());self.assertTrue(Path(material['path']).is_relative_to(destination))

class StockBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.home=self.root/'home'
        self.root_patch=patch.object(A,'private_root',return_value=self.root/'private');self.root_patch.start();self.addCleanup(self.root_patch.stop)
        self.home_patch=patch.object(Path,'home',return_value=self.home);self.home_patch.start();self.addCleanup(self.home_patch.stop)
        self.peers=patch.dict(A._peers,{},clear=True);self.peers.start();self.addCleanup(self.peers.stop)
        self.jobs=patch.dict(A._jobs,{},clear=True);self.jobs.start();self.addCleanup(self.jobs.stop)
        self.origin='chrome-extension://'+'a'*32

    def connect(self,owner):
        record=A.peer(owner,'artlist');A.bridge(record['token'],self.origin,dict(action='poll',account_state='connected'));return record

    def test_extension_progress_is_scoped_and_reports_only_real_byte_counts(self):
        record=self.connect('one');key=A.submit('one','artlist',dict(kind='broll',query='paper desk',start=4))
        A.bridge(record['token'],self.origin,dict(action='poll',account_state='connected'))
        A.bridge(record['token'],self.origin,dict(action='progress',job_id=key,stage='download',received=1024,total=2048))
        self.assertIn('50%',A.status('one',key)['message'])
        A.bridge(record['token'],self.origin,dict(action='progress',job_id=key,stage='download',received=-1,total=2048))
        self.assertNotIn('%',A.status('one',key)['message'])
        other=self.connect('two')
        with self.assertRaises(ValueError):A.bridge(other['token'],self.origin,dict(action='progress',job_id=key,stage='verify'))
        with self.assertRaises(ValueError):A.bridge(record['token'],self.origin,dict(action='progress',job_id=key,stage='arbitrary website text'))

    def test_open_browser_uses_normal_chrome_without_automation_or_debugger(self):
        record=A.peer('one','artlist')
        with patch.object(A,'chrome_binary',return_value='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),patch.object(A.subprocess,'Popen') as launch:
            A.open_browser(record)
        command=launch.call_args.args[0]
        joined=' '.join(command)
        for forbidden in ('remote-debugging','enable-automation','mock-keychain','password-store','disable-web-security'):self.assertNotIn(forbidden,joined)
        self.assertIn('--profile-directory=ChuayDai_',joined)
        self.assertIn('chrome://extensions/',command)

    def test_bridge_rejects_web_origin_and_unrecognized_token(self):
        record=A.peer('one','artlist')
        with self.assertRaises(ValueError):A.bridge(record['token'],'https://evil.test',dict(action='poll'))
        with self.assertRaises(ValueError):A.bridge('wrong',self.origin,dict(action='poll'))

    def test_only_paired_origin_can_use_scoped_peer(self):
        record=self.connect('one')
        with self.assertRaises(ValueError):A.bridge(record['token'],'chrome-extension://'+'b'*32,dict(action='poll'))
        self.assertEqual((record['root']/'bridge.json').stat().st_mode&0o777,0o600)

    def test_other_user_cannot_claim_job_or_submit_its_receipt(self):
        first=self.connect('one');second=self.connect('two')
        key=A.submit('one','artlist',dict(kind='broll',query='office workers',start=4))
        self.assertIsNone(A.bridge(second['token'],self.origin,dict(action='poll',account_state='connected'))['job'])
        claimed=A.bridge(first['token'],self.origin,dict(action='poll',account_state='connected'))['job'];self.assertEqual(claimed['id'],key)
        with self.assertRaises(ValueError):A.bridge(second['token'],self.origin,dict(action='result',job_id=key,error='captcha'))
        A.bridge(first['token'],self.origin,dict(action='result',job_id=key,error='token=do-not-echo'))
        self.assertNotIn('do-not-echo',json.dumps(A.status('one',key)))

    def test_receipt_outside_job_folder_is_rejected_and_valid_file_is_preserved(self):
        record=self.connect('one');key=A.submit('one','artlist',dict(kind='broll',query='office workers',start=4))
        A.bridge(record['token'],self.origin,dict(action='poll',account_state='connected'))
        data=dict(action='result',job_id=key,url='https://artlist.io/stock-footage/clip/office/1',filename=str(self.root/'elsewhere.mp4'),title='Office')
        with self.assertRaises(ValueError):A.bridge(record['token'],self.origin,data)
        import hashlib
        folder=self.home/'Downloads'/'ChuayDaiStock'/hashlib.sha256(b'one').hexdigest()[:16]/key;folder.mkdir(parents=True)
        media=folder/'clip.mp4';media.write_bytes(b'fixture')
        data['filename']=str(media)
        with patch.object(B,'verify_file',return_value=dict(duration=3,sha256='a'*64,size=7)) as verified:
            A.bridge(record['token'],self.origin,data)
            import time
            deadline=time.monotonic()+3
            while A.status('one',key)['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(Path(verified.call_args.args[0]).is_relative_to(record['root']/'media'))
        result=A.status('one',key)['result'];self.assertTrue(Path(result['path']).is_file());self.assertNotIn('token',result)

    def test_slow_verification_does_not_block_bridge_and_cancel_wins(self):
        import hashlib,time,threading
        record=self.connect('one');key=A.submit('one','artlist',dict(kind='broll',query='office workers',start=4))
        A.bridge(record['token'],self.origin,dict(action='poll',account_state='connected'))
        folder=self.home/'Downloads'/'ChuayDaiStock'/hashlib.sha256(b'one').hexdigest()[:16]/key;folder.mkdir(parents=True)
        media=folder/'clip.mp4';media.write_bytes(b'fixture')
        data=dict(action='result',job_id=key,url='https://artlist.io/stock-footage/clip/office/1',filename=str(media),title='Office')
        entered=threading.Event();release=threading.Event();finished=threading.Event()
        def verify(*args):
            entered.set();release.wait(3);finished.set()
            return dict(duration=3,sha256='a'*64,size=7)
        with patch.object(B,'verify_file',side_effect=verify) as mocked:
            try:
                started=time.monotonic();result=A.bridge(record['token'],self.origin,data)
                self.assertTrue(result['accepted']);self.assertLess(time.monotonic()-started,.5)
                self.assertTrue(entered.wait(1))
                self.assertTrue(A.bridge(record['token'],self.origin,data)['accepted'])
                self.assertEqual(mocked.call_count,1)
                self.assertEqual(A.status('one',key)['state'],'running')
                started=time.monotonic();A.bridge(record['token'],self.origin,dict(action='job_status',job_id=key))
                self.assertLess(time.monotonic()-started,.5)
                A.handle('one',dict(action='cancel',job_id=key))
            finally:release.set();finished.wait(2)
        time.sleep(.05)
        self.assertEqual(A.status('one',key)['state'],'failed')

    def test_disconnect_revokes_code_and_cancels_queued_job(self):
        record=self.connect('one');old=record['token'];key=A.submit('one','artlist',dict(kind='music',query='calm piano',start=0))
        A.handle('one',dict(action='disconnect',provider='artlist'))
        with self.assertRaises(ValueError):A.bridge(old,self.origin,dict(action='poll'))
        self.assertEqual(A.status('one',key)['state'],'failed')

    def test_manifest_does_not_request_cookie_or_debugger_permissions(self):
        manifest=json.loads((A.extension_dir()/'manifest.json').read_bytes())
        self.assertNotIn('cookies',manifest['permissions']);self.assertNotIn('debugger',manifest['permissions'])
        self.assertNotIn('<all_urls>',manifest['host_permissions'])
