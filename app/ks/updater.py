"""Verified macOS app updates with a durable backup and a detached installer."""
import base64,copy,hashlib,json,os,plistlib,re,shlex,shutil,stat,subprocess,sys,tempfile,threading,time,urllib.request,urllib.error,uuid,zipfile
from pathlib import Path
from .job_admission import install

GITHUB_USER='utccedit1'
GITHUB_REPO='SPKKB'
ASSET_NAME='SPKKB.app.zip'
VERSION_JSON_URL=f'https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/version.json'
BUNDLE_ID='ac.utcc.mediapro.chuaydai'
STATE_DIR=Path.home()/'.karaoke_studio'
RECEIPT=STATE_DIR/'update_install.json'

def _local_version():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
    try:return str(json.loads((root/'version.json').read_text())['version'])
    except (OSError,ValueError,KeyError):return '1.5.1'
CURRENT_VERSION=_local_version()

def _parse_version(value):
    value=str(value).strip().lstrip('v')
    if not re.fullmatch(r'\d+(?:\.\d+){0,2}',value):raise ValueError('หมายเลขเวอร์ชันไม่ถูกต้อง')
    parts=tuple(map(int,value.split('.')))
    return parts+(0,)*(3-len(parts))

def _get_app_bundle_path():
    if getattr(sys,'frozen',False):
        path=Path(sys.executable).resolve().parent.parent.parent
        if path.suffix=='.app':return path
    return None

def _request(url):
    return urllib.request.Request(url,headers={'User-Agent':'ChuaydaiStudio-Updater/1.5','Cache-Control':'no-cache'})

def check_for_update(timeout=12):
    try:
        try:
            url=f'https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/version.json?ref=main&t={int(time.time())}'
            with urllib.request.urlopen(_request(url),timeout=timeout) as response:
                envelope=json.loads(response.read())
            data=json.loads(base64.b64decode(envelope['content']))
        except (urllib.error.URLError,KeyError,ValueError):
            with urllib.request.urlopen(_request(VERSION_JSON_URL+'?t='+str(int(time.time()))),timeout=timeout) as response:
                data=json.loads(response.read())
        latest=str(data['version']);available=_parse_version(latest)>_parse_version(CURRENT_VERSION)
        url=str(data.get('download_url',''));checksum=str(data.get('sha256',''));size=int(data.get('size',0))
        if available:
            expected=f'https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/download/'
            if not url.startswith(expected) or not url.endswith('/'+ASSET_NAME):raise ValueError('ลิงก์ดาวน์โหลดไม่ตรงกับไฟล์ Release ของโปรแกรม')
            if not re.fullmatch('[0-9a-fA-F]{64}',checksum) or size<=0:raise ValueError('Release ยังไม่พร้อม: ต้องมีไฟล์แอป ขนาด และค่าตรวจสอบ SHA-256 กรุณาเผยแพร่ Release ให้ครบ')
        return {'available':available,'latest_version':latest,'current_version':CURRENT_VERSION,'download_url':url,'release_notes':str(data.get('release_notes','')),'sha256':checksum.lower(),'size':size,'install_supported':_get_app_bundle_path() is not None}
    except urllib.error.URLError as exc:return {'available':False,'error':'ตรวจอัปเดตไม่ได้: '+str(exc.reason)}
    except Exception as exc:return {'available':False,'error':str(exc)}

def download_update(download_url,progress_cb=None,expected_sha256=None,expected_size=None):
    folder=Path(tempfile.mkdtemp(prefix='studio_update_'));path=folder/ASSET_NAME
    try:
        digest=hashlib.sha256();count=0
        with urllib.request.urlopen(_request(download_url),timeout=75) as response,path.open('wb') as target:
            total=int(response.headers.get('Content-Length') or expected_size or 0)
            while True:
                chunk=response.read(256*1024)
                if not chunk:break
                count+=len(chunk)
                if expected_size and count>expected_size:raise ValueError('ขนาดไฟล์อัปเดตไม่ตรงกับ Release')
                target.write(chunk);digest.update(chunk)
                if progress_cb:progress_cb(count,total)
            target.flush();os.fsync(target.fileno())
        if count==0 or (expected_size and count!=expected_size) or (total and count!=total):raise ValueError('ดาวน์โหลดไม่ครบ กรุณาลองใหม่')
        if expected_sha256 and digest.hexdigest()!=expected_sha256.lower():raise ValueError('ไฟล์อัปเดตไม่ผ่านการตรวจ SHA-256 ยังไม่ได้เปลี่ยนโปรแกรม')
        if not zipfile.is_zipfile(path):raise ValueError('ไฟล์ที่ดาวน์โหลดไม่ใช่ชุดติดตั้งแอป')
        return path
    except Exception:
        shutil.rmtree(folder,ignore_errors=True);raise

def extract_app(archive,expected_version=None):
    destination=Path(archive).parent/'extracted';destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            name=item.filename
            if '\\' in name or name.startswith('/') or '..' in Path(name).parts:raise ValueError('ชุดติดตั้งมีตำแหน่งไฟล์ไม่ปลอดภัย')
            if stat.S_ISLNK(item.external_attr>>16):
                link=source.read(item).decode('utf-8');resolved=(destination/name).parent.joinpath(link).resolve()
                if not resolved.is_relative_to(destination.resolve()):raise ValueError('ชุดติดตั้งมีลิงก์ออกนอกโฟลเดอร์แอป')
        if source.testzip():raise ValueError('ชุดติดตั้งเสียหาย')
        if sys.platform=='darwin':
            subprocess.run(['/usr/bin/ditto','-x','-k',str(archive),str(destination)],check=True,capture_output=True)
        else:
            for item in source.infolist():
                target=destination/item.filename;mode=item.external_attr>>16
                if item.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                target.parent.mkdir(parents=True,exist_ok=True)
                if stat.S_ISLNK(mode):target.symlink_to(source.read(item).decode())
                else:
                    target.write_bytes(source.read(item))
                    if mode:target.chmod(stat.S_IMODE(mode))
    candidates=[p for p in destination.rglob('*.app') if '__MACOSX' not in p.parts and not any(parent.suffix=='.app' for parent in p.parents)]
    if len(candidates)!=1:raise ValueError('ต้องมีแอปหลักเพียงหนึ่งตัวในชุดติดตั้ง')
    app=candidates[0]
    with (app/'Contents/Info.plist').open('rb') as f:info=plistlib.load(f)
    if info.get('CFBundleIdentifier')!=BUNDLE_ID:raise ValueError('ชุดติดตั้งไม่ใช่โปรแกรมช่วยด้วยจ้า')
    if expected_version and _parse_version(info.get('CFBundleShortVersionString',''))!=_parse_version(expected_version):raise ValueError('เวอร์ชันในไฟล์แอปไม่ตรงกับ Release')
    executable=info.get('CFBundleExecutable','')
    if not executable or Path(executable).name!=executable or not (app/'Contents/MacOS'/executable).is_file():raise ValueError('ชุดติดตั้งไม่มีไฟล์เปิดโปรแกรม')
    if not os.access(app/'Contents/MacOS'/executable,os.X_OK):raise ValueError('ไฟล์เปิดโปรแกรมไม่มีสิทธิ์ทำงาน กรุณาสร้าง ZIP ด้วย ditto')
    if sys.platform=='darwin':
        result=subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True)
        if result.returncode:raise ValueError('ลายเซ็นชุดติดตั้งไม่ผ่าน กรุณาสร้างและลงนามแอปใหม่')
    return app

def _helper_text(app,staged,backup,receipt,pid,log,previous_app=None,trash_dir=None):
    q=shlex.quote
    previous_app=previous_app or app
    trash_dir=Path(trash_dir or Path.home()/'.Trash')
    trash_backup=trash_dir/(backup.stem+'-'+uuid.uuid4().hex[:8]+'.app')
    trash_previous=trash_dir/(previous_app.stem+'-old-'+uuid.uuid4().hex[:8]+'.app')
    installed=q(json.dumps({'state':'installed','backup':str(trash_backup),'installed_app':str(app),'previous_app':str(previous_app)},ensure_ascii=False))
    # Keep previous app intact until the new app has been completely staged.
    return f'''#!/bin/sh
set -eu
exec >>{q(str(log))} 2>&1
APP={q(str(app))}
STAGED={q(str(staged))}
BACKUP={q(str(backup))}
RECEIPT={q(str(receipt))}
PREVIOUS={q(str(previous_app))}
i=0
while kill -0 {int(pid)} 2>/dev/null; do
 i=$((i+1))
 if [ "$i" -gt 60 ]; then printf '%s' '{{"state":"error","error":"โปรแกรมเดิมยังไม่ปิด กรุณาปิดแล้วลองใหม่"}}' > "$RECEIPT"; exit 1; fi
 sleep 1
done
moved=0
installed_new=0
rollback() {{
 if [ "$installed_new" = 1 ] && [ -e "$APP" ]; then mv "$APP" "$STAGED.failed"; fi
 if [ "$moved" = 1 ]; then mv "$BACKUP" "$APP"; fi
 printf '%s' '{{"state":"error","error":"ติดตั้งไม่สำเร็จ คืนโปรแกรมเดิมแล้ว ดู update_install.log"}}' > "$RECEIPT"
 if [ "$moved" = 1 ]; then /usr/bin/open "$APP" || true; else /usr/bin/open "$PREVIOUS" || true; fi
}}
trap rollback HUP INT TERM
if [ -e "$APP" ]; then
 if ! mv "$APP" "$BACKUP"; then rollback; exit 1; fi
 moved=1
fi
if ! mv "$STAGED" "$APP"; then rollback; exit 1; fi
installed_new=1
if ! /usr/bin/open "$APP"; then rollback; exit 1; fi
trap - HUP INT TERM
# Installation succeeded: remove redundant apps from the visible app folders.
if mkdir -p {q(str(trash_dir))}; then
 if [ -e "$BACKUP" ]; then mv "$BACKUP" {q(str(trash_backup))} || true; fi
 if [ "$PREVIOUS" != "$APP" ] && [ -d "$PREVIOUS" ] && [ -w "$(dirname "$PREVIOUS")" ]; then
  case "$PREVIOUS" in /Volumes/*|*/AppTranslocation/*) ;; *) mv "$PREVIOUS" {q(str(trash_previous))} || true ;; esac
 fi
fi
LS_REGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
if [ -x "$LS_REGISTER" ]; then
 "$LS_REGISTER" -u "$BACKUP" || true
 "$LS_REGISTER" -u {q(str(trash_backup))} || true
 if [ "$PREVIOUS" != "$APP" ]; then
  "$LS_REGISTER" -u "$PREVIOUS" || true
  "$LS_REGISTER" -u {q(str(trash_previous))} || true
 fi
 "$LS_REGISTER" -f "$APP" || true
fi
printf '%s' {installed} > "$RECEIPT"
'''

def _probe_install_directory(directory):
    """Test actual creation rather than trusting os.access on protected mounts."""
    directory=Path(directory)
    try:
        directory.mkdir(parents=True,exist_ok=True)
        probe=Path(tempfile.mkdtemp(prefix='.studio-write-test-',dir=directory))
        probe.rmdir()
        return True
    except OSError:
        return False


def _installation_target(current_app):
    current_app=Path(current_app)
    installed_dirs=(Path('/Applications'),Path.home()/'Applications')
    # An installed app stays at exactly the same path/name. Never silently make
    # a second copy when that location is protected or occupied by another app.
    if current_app.parent in installed_dirs:
        target=current_app
    else:
        existing=[d/'ช่วยด้วยจ้า.app' for d in installed_dirs if (d/'ช่วยด้วยจ้า.app').exists()]
        target=existing[0] if existing else Path.home()/'Applications/ช่วยด้วยจ้า.app'
    if target.is_symlink():raise ValueError('ตำแหน่งติดตั้งเป็นลิงก์ กรุณาเลือกตำแหน่งแอปจริงก่อนอัปเดต')
    if target.exists():
        try:
            info=plistlib.loads((target/'Contents/Info.plist').read_bytes())
            if info.get('CFBundleIdentifier')!=BUNDLE_ID:raise ValueError('ชื่อไฟล์ซ้ำกับแอปอื่น จะไม่เขียนทับ')
        except (OSError,plistlib.InvalidFileException) as exc:
            raise ValueError('ไฟล์ในตำแหน่งติดตั้งไม่ใช่แอปที่อัปเดตได้ จะไม่เขียนทับ') from exc
    if not _probe_install_directory(target.parent):
        raise ValueError('อัปเดตในตำแหน่งเดิมไม่ได้ กรุณาตรวจสิทธิ์ Applications และพื้นที่ว่าง ระบบจะไม่สร้างแอปอีกตัว')
    return target


def apply_update(zip_path,expected_version=None,wait_pid=None,exit_application=True):
    current_app=_get_app_bundle_path()
    if current_app is None:raise ValueError('เปิดโปรแกรมจากไฟล์ .app จึงจะอัปเดตตัวเองได้ โหมดรัน Python ให้ใช้ Git หรือไฟล์ติดตั้งรุ่นใหม่')
    new_app=extract_app(zip_path,expected_version)
    app=_installation_target(current_app)
    suffix=uuid.uuid4().hex[:8]
    staged=app.parent/('.'+app.stem+'.update-'+suffix+'.app')
    backup=app.parent/(app.stem+'.backup-'+time.strftime('%Y%m%d-%H%M%S')+'-'+suffix+'.app')
    try:
        subprocess.run(['/usr/bin/ditto',str(new_app),str(staged)],check=True,capture_output=True)
        # For relocation with no previous installed target, preserve the running app
        # in the writable destination before asking it to quit.
        if app!=current_app and not app.exists():
            subprocess.run(['/usr/bin/ditto',str(current_app),str(backup)],check=True,capture_output=True)
        STATE_DIR.mkdir(parents=True,exist_ok=True)
        RECEIPT.write_text(json.dumps({'state':'prepared','version':expected_version,'backup':str(backup),'installed_app':str(app),'previous_app':str(current_app)},ensure_ascii=False))
        helper=Path(zip_path).parent/'install.sh'
        helper.write_text(_helper_text(app,staged,backup,RECEIPT,wait_pid if wait_pid is not None else os.getpid(),STATE_DIR/'update_install.log',current_app))
        helper.chmod(0o700)
        subprocess.Popen(['/bin/sh',str(helper)],start_new_session=True,close_fds=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    except Exception:
        shutil.rmtree(staged,ignore_errors=True)
        # Source and installed app have not been changed at this stage.
        raise
    if exit_application:
        timer=threading.Timer(1.0,lambda:os._exit(0));timer.daemon=True;timer.start()
    return True

def cleanup_legacy_backups(current_app=None,trash_dir=None):
    """Only retire this application's older updater backups; never other apps."""
    app=Path(current_app) if current_app else _get_app_bundle_path()
    if app is None:return []
    trash=Path(trash_dir or Path.home()/'.Trash');moved=[]
    for candidate in app.parent.glob(app.stem+'.backup-*.app'):
        if candidate.is_symlink():continue
        try:
            info=plistlib.loads((candidate/'Contents/Info.plist').read_bytes())
            if info.get('CFBundleIdentifier')!=BUNDLE_ID:continue
            if _parse_version(info.get('CFBundleShortVersionString',''))>=_parse_version(CURRENT_VERSION):continue
            trash.mkdir(parents=True,exist_ok=True)
            target=trash/(candidate.stem+'-'+uuid.uuid4().hex[:8]+'.app')
            shutil.move(str(candidate),str(target));moved.append(str(target))
        except (OSError,ValueError,plistlib.InvalidFileException):continue
    return moved

class UpdateManager:
    def __init__(self):
        self._lock=threading.Lock();self.state='idle';self.progress=0;self.info={};self.error='';self.bytes_downloaded=0;self.bytes_total=0
    def get_status(self):
        with self._lock:return copy.deepcopy({k:getattr(self,k) for k in ('state','progress','info','error','bytes_downloaded','bytes_total')})
    def _set(self,**values):
        with self._lock:
            for key,value in values.items():setattr(self,key,value)
    def check_async(self):
        with self._lock:
            if self.state in ('checking','downloading','applying'):return False
            self.state='checking';self.error=''
        def run():
            result=check_for_update()
            self._set(state='error' if result.get('error') else 'update_available' if result['available'] else 'up_to_date',info=result,error=result.get('error',''))
        threading.Thread(target=run,daemon=True,name='update-check').start();return True
    @install
    def download_and_apply_async(self):
        from . import event_jobs
        with event_jobs._lock:
            if any(job.get('state') in ('queued','running') for job in event_jobs._jobs.values()):
                self._set(error='มีงานตัดคลิปหรือจัดซับกำลังทำอยู่ กรุณารอจนเสร็จก่อนอัปเดต')
                return False
            with self._lock:
                if self.state!='update_available':return False
                if _get_app_bundle_path() is None:
                    self.state='error';self.error='เปิดไฟล์ .app รุ่นใหม่เพื่อติดตั้งอัปเดต โหมด Python ไม่สามารถแทนที่ตัวโปรแกรมได้';return False
                info=copy.deepcopy(self.info);self.state='downloading';self.progress=0;self.error=''
        def run():
            try:
                def progress(downloaded,total):self._set(progress=min(90,int(downloaded/total*90)) if total else 0,bytes_downloaded=downloaded,bytes_total=total)
                archive=download_update(info['download_url'],progress,info['sha256'],info['size'])
                self._set(state='applying',progress=95)
                if not apply_update(archive,info['latest_version']):raise ValueError('ติดตั้งไม่สำเร็จ')
            except Exception as exc:self._set(state='error',error=str(exc))
            finally:
                from .job_admission import installation_finished
                installation_finished()
        threading.Thread(target=run,daemon=True,name='update-install').start();return True

update_manager=UpdateManager()
