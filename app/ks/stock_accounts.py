"""Scoped local bridge to a user-installed extension in normal Chrome.

No provider password, cookie, OAuth token or signed media URL is read by the app.
"""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from . import job_store

PROVIDERS={'artlist':{'name':'Artlist','home':'https://artlist.io/stock-footage'},'envato':{'name':'Envato','home':'https://app.envato.com/stock-video'}}
_jobs={};_peers={};_lock=threading.RLock()
JOB_TIMEOUT=480

class StockDownloadError(ValueError):
    def __init__(self,message,code):
        super().__init__(message);self.code=code


def cached_download(owner,p,request):
    from .stock_browser import safe_item,verify_file,StockError
    root=peer(owner,provider(p))['root']/'media'
    if not root.is_dir():return None
    for receipt in sorted(root.glob('*.stock.json'),key=lambda f:f.stat().st_mtime,reverse=True)[:500]:
        try:
            saved=json.loads(receipt.read_bytes())
            if saved.get('url') in request.get('exclude_urls',[]) or saved.get('sha256') in request.get('exclude_hashes',[]):continue
            if saved.get('kind')!=request.get('kind') or saved.get('provider')!=p or not safe_item(saved.get('url',''),request['kind']):continue
            exact=saved.get('query')==request.get('query')
            if not exact:
                if request.get('kind')!='broll':continue
                import re
                words=lambda value:{w.rstrip('s') for w in re.findall(r'[a-z]{3,}',str(value).lower())}
                terms=words(request.get('query',''))-{'stock','footage','video','portrait','vertical','with','and','the'}
                title=words(saved.get('title',''));required={w.rstrip('s') for w in request.get('required_terms',[])}
                if not terms or not required or not required.issubset(title) or len(terms&title)/len(terms)<.6:continue
            path=Path(saved['path']).resolve()
            if path.parent!=root.resolve() or receipt.resolve()!=path.with_suffix(path.suffix+'.stock.json'):continue
            checked=verify_file(path,request['kind'])
            if checked['sha256']!=saved.get('sha256'):continue
            return dict(saved,**checked)
        except (OSError,ValueError,KeyError,TypeError):continue
    return None


def timeout_message(job):
    stage=job.get('stage')
    query=(job.get('request') or {}).get('query','')
    detail={'search':'ค้างระหว่างค้นหาหรือเลือกสื่อ ยังไม่ได้ดาวน์โหลด','selected':'เลือกสื่อแล้ว แต่ยังไม่เริ่มดาวน์โหลด','download':'กดดาวน์โหลดแล้ว แต่ยังไม่ได้ไฟล์ครบ','verify':'ได้รับไฟล์แล้ว แต่ตรวจไฟล์ไม่เสร็จ'}.get(stage,'ยังไม่ได้รับงานจากส่วนขยาย')
    return 'หมดเวลารอ · '+detail+(' · คำค้น: '+query if query else '')+' · เปิด Artlist และตรวจส่วนขยายก่อนลองใหม่'


def private_root():return Path.home()/'.karaoke_studio'/'stock_private'


def provider(value):
    if value not in PROVIDERS:raise ValueError('เลือก Artlist หรือ Envato')
    return value


def user_root(owner):
    if not isinstance(owner,str) or not owner:raise ValueError('กรุณาเข้าสู่ระบบ')
    root=private_root()/hashlib.sha256(owner.encode()).hexdigest()
    root.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(private_root(),0o700);os.chmod(root,0o700)
    return root


def extension_dir():return Path(__file__).resolve().parents[1]/'stock_extension'


def runtime():return extension_dir().joinpath('manifest.json').is_file()


def peer(owner,p):
    provider(p);key=(owner,p)
    with _lock:
        if key not in _peers:
            root=user_root(owner)/p;root.mkdir(exist_ok=True,mode=0o700);file=root/'bridge.json'
            if file.is_file():record=json.loads(file.read_bytes())
            else:
                record=dict(token=secrets.token_urlsafe(32),extension_origin=None)
                file.write_text(json.dumps(record),encoding='utf-8');os.chmod(file,0o600)
            record['owner']=owner
            from .ce_config import _atomic_json
            _atomic_json(str(file),{k:record[k] for k in ('token','extension_origin','download_root','owner','download_verified_at','browser_mode') if k in record})
            _peers[key]=dict(record,owner=owner,provider=p,state='not_open',message='ยังไม่ได้เชื่อมส่วนขยาย',seen=0,root=root)
        return _peers[key]


def public_status(owner):
    with _lock:
        values=[]
        for p,info in PROVIDERS.items():
            record=_peers.get((owner,p),{})
            saved=private_root()/hashlib.sha256(owner.encode()).hexdigest()/p/'bridge.json'
            if not record and saved.is_file():record=peer(owner,p)
            if record.get('state')=='connected' and time.time()-record.get('seen',0)>75:
                record=dict(record,state='needs_setup',message='เปิด Chrome ที่เชื่อมไว้เพื่อตรวจบัญชีอีกครั้ง')
            values.append(dict(provider=p,name=info['name'],state=record.get('state','not_open'),message=record.get('message','ยังไม่ได้เชื่อมส่วนขยาย'),automatic_supported=p=='artlist',download_verified_at=record.get('download_verified_at'),browser_mode=record.get('browser_mode','dedicated')))
        return dict(ok=True,runtime_available=runtime(),providers=values)


def chrome_binary():
    if sys.platform=='darwin':
        p=Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        if p.is_file():return str(p)
    if sys.platform=='win32':
        for variable in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA'):
            p=Path(os.environ.get(variable,''))/'Google/Chrome/Application/chrome.exe'
            if p.is_file():return str(p)
    return shutil.which('google-chrome') or shutil.which('google-chrome-stable')


def open_browser(record,setup=True):
    binary=chrome_binary()
    if not binary:raise ValueError('ไม่พบ Google Chrome กรุณาติดตั้ง Chrome ก่อนเชื่อมคลังสื่อ')
    # A named dedicated profile in normal Chrome stays in the same browser process,
    # so Chrome can show/activate it reliably on macOS. Never read other profiles.
    profile_name='ChuayDai_'+hashlib.sha256((record['owner']+':'+record['provider']).encode()).hexdigest()[:20]
    command=[binary,*(['--profile-directory='+profile_name] if record.get('browser_mode','dedicated')=='dedicated' else []),'--no-first-run','--new-window','chrome://extensions/' if setup else PROVIDERS[record['provider']]['home']]
    subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    record.update(state='needs_setup' if setup else 'not_open',message='เปิด Chrome แล้ว รอส่วนขยายตรวจบัญชีของคุณ',last_open=time.time())


def pairing(owner,p,base,browser_mode=None):
    record=peer(owner,p)
    if browser_mode is not None:
        if browser_mode not in ('existing','dedicated'):raise ValueError('เลือกรูปแบบ Chrome ไม่ถูกต้อง')
        record['browser_mode']=browser_mode
        from .ce_config import _atomic_json
        _atomic_json(str(record['root']/'bridge.json'),{k:record[k] for k in ('token','extension_origin','download_root','owner','download_verified_at','browser_mode') if k in record})
    open_browser(record)
    if not base.startswith('http://127.0.0.1:'):raise ValueError('ใช้การเชื่อมในเครื่องเท่านั้น')
    code=base64.urlsafe_b64encode(json.dumps(dict(base=base,token=record['token'],provider=p)).encode()).decode()
    return dict(ok=True,pairing_code=code,extension_folder=str(extension_dir()),message=record['message'])


def status(owner,token):
    with _lock:
        job=_jobs.get(token) or job_store.load(owner,'stock',token)
        if not job or job['owner']!=owner:raise ValueError('ไม่พบงานของผู้ใช้นี้')
        if job['state'] in ('queued','running') and time.time()-job['created']>JOB_TIMEOUT:
            job.update(state='failed',message=timeout_message(job),error_code='timeout')
            job_store.save('stock',token,job)
        return dict(ok=True,**{k:v for k,v in job.items() if k not in ('owner','created','request')})


from .job_admission import admit

@admit
def submit(owner,p,request):
    provider(p);record=peer(owner,p)
    if p!='artlist':raise ValueError('ดาวน์โหลดอัตโนมัติเริ่มรองรับ Artlist ก่อน')
    with _lock:
        if record['state']!='connected' or time.time()-record['seen']>75:raise ValueError('กรุณาเปิด Chrome ที่เชื่อมส่วนขยายและตรวจบัญชี Artlist ก่อน')
        for expired_token,job in _jobs.items():
            if job['state'] in ('queued','running') and time.time()-job['created']>JOB_TIMEOUT:
                job.update(state='failed',message=timeout_message(job),error_code='timeout')
                job_store.save('stock',expired_token,job)
        if any(j['owner']==owner and j['state'] in ('queued','running') for j in _jobs.values()):raise ValueError('มีงานสื่อกำลังทำอยู่ กรุณารอให้เสร็จ')
        for stale in list(_jobs):
            if time.time()-_jobs[stale]['created']>1800 and _jobs[stale]['state'] in ('done','failed'):del _jobs[stale]
        token=uuid.uuid4().hex
        _jobs[token]=dict(owner=owner,provider=p,state='queued',message='รอส่วนขยายค้นและดาวน์โหลด',request=request,created=time.time())
        try:job_store.save('stock',token,_jobs[token])
        except Exception:
            _jobs.pop(token,None)
            raise
        return token


def wait_download(owner,p,request,progress):
    cached=cached_download(owner,p,request)
    if cached:
        progress('ใช้ไฟล์ที่ดาวน์โหลดและตรวจไว้แล้ว: '+cached.get('title',''))
        return cached
    token=submit(owner,p,request);deadline=time.monotonic()+JOB_TIMEOUT
    try:
        while time.monotonic()<deadline:
            job=status(owner,token);progress('คำค้น: '+request['query']+' · '+job['message'])
            if job['state']=='done':return job['result']
            if job['state']=='failed':
                if job.get('error_code')=='no_match':return None
                raise StockDownloadError(job['message'],job.get('error_code','unknown'))
            time.sleep(.5)
        with _lock:
            _jobs[token].update(state='failed',message=timeout_message(_jobs[token]),error_code='timeout')
            job_store.save('stock',token,_jobs[token])
        raise StockDownloadError(_jobs[token]['message'],'timeout')
    except BaseException:
        # Parent cancellation/failure must stop the bridge too. Reject late receipts.
        with _lock:
            job=_jobs.get(token)
            if job and job['state'] in ('queued','running'):
                job.update(state='failed',message='งานหลักหยุดแล้ว ยกเลิกการรอสื่อนี้',error_code='cancelled')
                job_store.save('stock',token,job)
        raise


def bridge(token,origin,data):
    """Extension-only endpoint, separate from app login and project APIs."""
    from .stock_browser import safe_item,verify_file,StockError
    if not isinstance(token,str) or not origin.startswith('chrome-extension://') or len(origin)>100:raise ValueError('การเชื่อมส่วนขยายไม่ถูกต้อง')
    with _lock:
        # Reload known peers after app restart without printing account file contents.
        for file in private_root().glob('*/*/bridge.json'):
            try:
                record=json.loads(file.read_bytes())
                if hmac.compare_digest(record.get('token',''),token):
                    matching=next((p for p in _peers.values() if hmac.compare_digest(p['token'],token)),None)
                    if matching is None and record.get('owner') and hashlib.sha256(record['owner'].encode()).hexdigest()==file.parent.parent.name:
                        matching=peer(record['owner'],file.parent.name)
                    if matching is None:raise ValueError('เปิดหน้าบัญชีในแอปก่อนเชื่อมใหม่')
                    break
            except (OSError,json.JSONDecodeError):continue
        else:raise ValueError('รหัสเชื่อมไม่ถูกต้อง')
        record=matching
        if record.get('extension_origin') not in (None,origin):raise ValueError('รหัสนี้เชื่อมกับส่วนขยายอื่นอยู่ กรุณาล้างการเชื่อมในแอปก่อน')
        if record.get('extension_origin') is None:
            record['extension_origin']=origin;f=record['root']/'bridge.json'
            f.write_text(json.dumps({k:record[k] for k in ('token','extension_origin','download_root','owner','download_verified_at','browser_mode') if k in record}));os.chmod(f,0o600)
        record['seen']=time.time()
        action=data.get('action')
        if action=='poll':
            account_state=data.get('account_state')
            record['state']='connected' if account_state=='connected' else 'needs_login'
            record['message']='ส่วนขยายเชื่อมแล้ว และตรวจพบหน้าบัญชี' if account_state=='connected' else {'captcha':'Artlist ขอให้ยืนยัน CAPTCHA ด้วยตัวเองใน Chrome','needs_login':'กรุณาล็อกอิน Artlist ใน Chrome โปรไฟล์ที่เชื่อมไว้','account_not_found':'ยังไม่พบเมนูบัญชีในหน้าเว็บ ลองเปิดหน้า Artlist หลักแล้วตรวจอีกครั้ง'}.get(data.get('account_reason'),'กำลังรอหน้า Artlist พร้อมใช้งาน')
            job=next(((k,j) for k,j in _jobs.items() if j['owner']==record['owner'] and j['provider']==record['provider'] and j['state']=='queued'),None)
            if job and record['state']=='connected':
                key,j=job;j.update(state='running',message='ส่วนขยายกำลังค้นสื่อ');job_store.save('stock',key,j)
                folder='ChuayDaiStock/'+hashlib.sha256(record['owner'].encode()).hexdigest()[:16]+'/'+key
                return dict(ok=True,job=dict(id=key,**j['request'],download_folder=folder))
            return dict(ok=True,job=None)
        if action=='heartbeat':
            job=_jobs.get(data.get('job_id'))
            if not job or job['owner']!=record['owner'] or job['provider']!=record['provider'] or job['state']!='running':raise ValueError('งานสื่อนี้จบแล้ว')
            job['heartbeat_at']=time.time()
            return dict(ok=True)
        if action=='progress':
            job=_jobs.get(data.get('job_id'))
            if not job or job['owner']!=record['owner'] or job['provider']!=record['provider'] or job['state']!='running':raise ValueError('ไม่พบงานสื่อของบัญชีนี้')
            messages={'search':'กำลังค้นหา','selected':'พบสื่อแล้ว กำลังเปิดหน้าดาวน์โหลด','download':'กำลังดาวน์โหลดไฟล์','verify':'ดาวน์โหลดครบแล้ว กำลังตรวจไฟล์'}
            stage=data.get('stage')
            if stage not in messages:raise ValueError('สถานะสื่อไม่ถูกต้อง')
            if job.get('verifying'):return dict(ok=True)
            message=messages[stage]
            attempt=data.get('attempt')
            if stage in ('search','selected') and type(attempt) is int and 1<attempt<=3:
                message+=f' · รอหน้าเว็บพร้อม ครั้งที่ {attempt}/3'
            received,total=data.get('received'),data.get('total')
            if stage=='download' and all(isinstance(n,(int,float)) and not isinstance(n,bool) and 0<=n<=100*1024**3 for n in (received,total)) and total>0 and received<=total:
                message+=f' {received/total*100:.0f}% ({received/1024**2:.1f}/{total/1024**2:.1f} MB)'
            job.update(message=message,stage=stage,updated=time.time());job_store.save('stock',data['job_id'],job)
            return dict(ok=True)
        if action=='job_status':
            job=_jobs.get(data.get('job_id'))
            if not job or job['owner']!=record['owner']:return dict(ok=True,state='missing')
            return dict(ok=True,state=job['state'])
        if action!='result':raise ValueError('คำสั่งส่วนขยายไม่รองรับ')
        key=data.get('job_id');job=_jobs.get(key)
        if not job or job['owner']!=record['owner'] or job['provider']!=record['provider'] or job['state']!='running':raise ValueError('ไม่พบงานที่กำลังทำของบัญชีนี้')
        if data.get('error'):
            diagnostic=data.get('control_debug')
            if isinstance(diagnostic,dict):job['control_debug']={k:diagnostic[k] for k in ('formats','primary','opened') if type(diagnostic.get(k)) is int and 0<=diagnostic[k]<=1000}
            # Never echo arbitrary website text, URLs, tokens or account names.
            reason={'page_not_ready':'ยังไม่พบรายการผลค้นหา Artlist หลังลองกู้หน้าค้นหาแล้ว ยังไม่ได้เริ่มดาวน์โหลด','needs_login':'กรุณาล็อกอินใน Chrome','captcha':'Artlist ขอให้คุณยืนยัน CAPTCHA เอง','no_match':'ไม่พบสื่อที่ตรงคำค้น','download_controls':'หน้าดาวน์โหลดเปลี่ยน กรุณาตรวจเว็บ','preview':'พบไฟล์ตัวอย่าง จึงยังไม่ดาวน์โหลด','download_failed':'ส่วนขยายหยุดก่อนรับไฟล์สำเร็จ กรุณาตรวจหน้า Artlist','search_failed':'หน้าเว็บไม่ตอบสนองระหว่างค้นหา ยังไม่ได้เริ่มดาวน์โหลด','download_controls':'ไม่พบปุ่มดาวน์โหลดที่รองรับบนหน้าเว็บ'}.get(data['error'],'ส่วนขยายรับสื่อไม่สำเร็จ กรุณาตรวจหน้าต่างเว็บ')
            job.update(state='failed',message=reason,error_code=data['error'] if data['error'] in ('no_match','page_not_ready','search_failed','needs_login','captcha','download_controls','download_failed') else 'download_failed');job_store.save('stock',key,job);return dict(ok=True)
        url=str(data.get('url',''));kind=job['request']['kind']
        if not safe_item(url,kind):raise ValueError('แหล่งสื่อไม่ถูกต้อง')
        # Validate lexical scope immediately; canonical paths and file IO are checked
        # in the verifier, outside the bridge lock and the browser's 15s request.
        path=Path(os.path.abspath(str(data.get('filename',''))))
        expected=Path(os.path.abspath(str(Path(record.get('download_root') or str(Path.home()/'Downloads'))/'ChuayDaiStock'/hashlib.sha256(record['owner'].encode()).hexdigest()[:16]/key)))
        if not path.is_relative_to(expected):raise ValueError('ไฟล์ดาวน์โหลดอยู่นอกโฟลเดอร์ของงานนี้')
        if job.get('verifying'):return dict(ok=True,accepted=True)
        job.update(verifying=True,stage='verify',verify_started=time.time(),message='ดาวน์โหลดครบแล้ว กำลังคัดลอกเข้าพื้นที่แอปเพื่อตรวจไฟล์')
        job_store.save('stock',key,job)
        # All owner/path inputs are explicit; verification must not depend on the
        # webview's request-session capture (extension requests have no app session).
        try:
            threading.Thread(target=_verify_receipt,args=(key,job,dict(record),dict(data),path,expected,kind),name='stock-verify-'+key[:8],daemon=True).start()
        except Exception:
            job.update(state='failed',verifying=False,message='เริ่มตัวตรวจไฟล์ไม่ได้ กรุณาลองทดสอบดาวน์โหลดใหม่')
            job_store.save('stock',key,job)
            raise ValueError(job['message'])
        return dict(ok=True,accepted=True)


def _copy_deadline(key,job):
    # macOS can suspend open(Downloads) while waiting for a privacy decision.
    # Keep the UI responsive and never commit a late result after this deadline.
    with _lock:
        if _jobs.get(key) is job and job['state']=='running' and job.get('verify_step')=='starting':
            job.update(state='failed',verifying=False,error_code='file_access_timeout',message='ดาวน์โหลดเสร็จแล้ว แต่แอปอ่านไฟล์ไม่ได้ภายใน 30 วินาที · ไปที่บัญชีคลังสื่อ แล้วกด “เลือกโฟลเดอร์ดาวน์โหลดให้แอปอ่าน” หากสวิตช์ Downloads Folder เปิดอยู่แล้ว สิทธิ์อาจยังผูกกับแอปรุ่นก่อน')
            job_store.save('stock',key,job)


def _verify_receipt(key,job,record,data,path,expected,kind):
    from .stock_browser import verify_file,StockError
    temporary=None
    deadline=threading.Timer(30,_copy_deadline,args=(key,job));deadline.daemon=True
    try:
        with _lock:
            job['verify_step']='starting';job_store.save('stock',key,job)
        deadline.start()
        path=path.resolve();expected=expected.resolve()
        if not path.is_relative_to(expected):raise ValueError('outside job folder')
        destination=record['root']/'media';destination.mkdir(exist_ok=True,mode=0o700)
        # The app reads Downloads once. Its child ffprobe reads only the private copy,
        # avoiding a second macOS file-access prompt in a background subprocess.
        if path.stat().st_size>350*1024*1024:raise StockError('ไฟล์สื่อเกิน 350 MB จึงยังไม่นำเข้า')
        temporary=destination/('.'+uuid.uuid4().hex+'_'+path.name)
        shutil.copyfile(path,temporary)
        with _lock:
            if _jobs.get(key) is not job or job['state']!='running':return
            job.update(message='คัดลอกไฟล์แล้ว กำลังตรวจชนิดสื่อและความยาว',stage='verify',verify_step='probing')
            job_store.save('stock',key,job)
        deadline.cancel()
        metadata=verify_file(temporary,kind)
        target=destination/(metadata['sha256']+path.suffix.lower())
        if not target.is_file():os.replace(temporary,target)
        url=str(data['url'])
        result=dict(path=str(target),provider=record['provider'],url=url,title=str(data.get('title',''))[:240],query=job['request']['query'],kind=kind,license_status='downloaded_via_own_account',license_verified=False,acquired_at=time.time(),catalog_path=url.split('artlist.io',1)[-1],**metadata)
        from .ce_config import _atomic_json
        _atomic_json(str(target.with_suffix(target.suffix+'.stock.json')),result)
        with _lock:
            if _jobs.get(key) is not job or job['state']!='running':return
            job.update(state='done',message='ดาวน์โหลดและตรวจไฟล์จริงแล้ว',result=result,verifying=False)
            job_store.save('stock',key,job)
            live=_peers.get((record['owner'],record['provider']))
            if live is not None:
                live['download_verified_at']=time.time()
                try:_atomic_json(str(live['root']/'bridge.json'),{k:live[k] for k in ('token','extension_origin','download_root','owner','download_verified_at','browser_mode') if k in live})
                except OSError:pass
    except Exception as exc:
        with _lock:
            if _jobs.get(key) is job and job['state']=='running':
                message=str(exc) if isinstance(exc,StockError) else ('แอปอ่านโฟลเดอร์ดาวน์โหลดไม่ได้ กรุณาตรวจสิทธิ์ไฟล์ของแอป' if isinstance(exc,PermissionError) else 'ไฟล์สื่อจริงไม่ผ่านการตรวจ จึงยังไม่นำเข้าโปรเจกต์')
                job.update(state='failed',message=message,verifying=False)
                job_store.save('stock',key,job)

    finally:
        deadline.cancel()
        if temporary is not None:temporary.unlink(missing_ok=True)

def handle(owner,data,base='http://127.0.0.1:8765'):
    action=data.get('action');p=data.get('provider')
    if action=='status':return public_status(owner)
    if action=='job_status':return status(owner,data.get('job_id'))
    if action=='cancel':
        with _lock:
            job=_jobs.get(data.get('job_id'))
            if not job or job['owner']!=owner:raise ValueError('ไม่พบงานของผู้ใช้นี้')
            if job['state'] in ('queued','running'):
                job.update(state='failed',message='ยกเลิกงานแล้ว')
                job_store.save('stock',data['job_id'],job)
        return dict(ok=True,message='ยกเลิกงานแล้ว')
    if action=='connect':return pairing(owner,provider(p),base,data.get('browser_mode'))
    if action=='test_download':
        kind=data.get('kind','broll')
        if kind not in ('broll','music'):raise ValueError('ประเภทสื่อไม่ถูกต้อง')
        request=dict(kind=kind,query='calendar' if kind=='broll' else 'calm instrumental',start=0,duration=3)
        return dict(ok=True,job_id=submit(owner,provider(p),request))
    if action=='authorize_downloads':
        record=peer(owner,provider(p))
        root=Path(record.get('download_root') or str(Path.home()/'Downloads')).resolve()
        webview=sys.modules.get('webview')
        if webview is None or not webview.windows:
            raise ValueError('กรุณาใช้ปุ่มนี้ในแอปช่วยด้วยจ้าบนเครื่อง เพื่อเปิดหน้าต่างเลือกโฟลเดอร์ของ macOS')
        selected=webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER,directory=str(root))
        if not selected:return dict(ok=True,message='ยกเลิกการเลือกโฟลเดอร์แล้ว')
        if Path(selected[0]).resolve()!=root:
            raise ValueError('กรุณาเลือกโฟลเดอร์ดาวน์โหลดเดียวกับ Chrome: '+str(root))
        return dict(ok=True,message='เลือกโฟลเดอร์ให้แอปอ่านแล้ว กรุณาทดสอบดาวน์โหลดอีกครั้ง หากเพิ่งอัปเดตให้ใช้ปุ่มนี้เมื่อ macOS ยังจำสิทธิ์รุ่นเก่า')
    if action=='download_root':
        root=Path(str(data.get('path',''))).expanduser().resolve()
        if not root.is_dir():raise ValueError('ไม่พบโฟลเดอร์ดาวน์โหลด กรุณาเลือกโฟลเดอร์เดียวกับ Chrome')
        record=peer(owner,provider(p))
        record['download_root']=str(root)
        file=record['root']/'bridge.json'
        from .ce_config import _atomic_json
        _atomic_json(str(file),{k:record[k] for k in ('token','extension_origin','download_root','owner','download_verified_at','browser_mode') if k in record})
        return dict(ok=True,message='บันทึกโฟลเดอร์แล้ว ตั้งค่า Download location ใน Chrome ให้ตรงกัน: '+str(root))
    if action not in ('check','disconnect'):raise ValueError('คำสั่งบัญชีไม่รองรับ')
    record=peer(owner,provider(p))
    if action=='check':
        if time.time()-record['seen']>75:raise ValueError('ยังไม่พบส่วนขยาย กรุณาติดตั้งและวางรหัสเชื่อมใน Chrome ก่อน')
        if record['state']!='connected':raise ValueError(record['message'])
        return dict(ok=True,message=record['message'],download_verified_at=record.get('download_verified_at'),browser_mode=record.get('browser_mode','dedicated'))
    if action=='disconnect':
        # Revoke only the app bridge. The extension never has cookie/password permissions.
        record.update(token=secrets.token_urlsafe(32),extension_origin=None,state='not_open',message='ยกเลิกสิทธิ์ส่วนขยายแล้ว ออกจากบัญชีเว็บได้ใน Chrome')
        f=record['root']/'bridge.json';f.write_text(json.dumps({k:record[k] for k in ('token','extension_origin','download_root','owner','download_verified_at','browser_mode') if k in record}));os.chmod(f,0o600)
        for job in _jobs.values():
            if job['owner']==owner and job['provider']==p and job['state'] in ('queued','running'):job.update(state='failed',message='ยกเลิกการเชื่อมบัญชีแล้ว')
        return dict(ok=True,message=record['message'])
    raise ValueError('คำสั่งบัญชีไม่รองรับ')


def shutdown():pass


def ensure_ready(owner,p,progress,timeout=45):
    record=peer(owner,provider(p));deadline=time.monotonic()+timeout
    if (record['state']!='connected' or time.time()-record['seen']>75) and time.time()-record.get('last_open',0)>45:
        open_browser(record,setup=False)
    while time.monotonic()<deadline:
        with _lock:
            if record['state']=='connected' and time.time()-record['seen']<=75:return
        progress('กำลังรอส่วนขยายเชื่อม Artlist หลังเปิดแอปใหม่ กรุณาเปิด Chrome โปรไฟล์ที่เชื่อมไว้')
        time.sleep(.5)
    raise ValueError('ยังไม่พบ Artlist ที่ล็อกอิน กรุณาเปิด Chrome ที่เชื่อมไว้แล้วกดตรวจการเชื่อมก่อนลองใหม่')
