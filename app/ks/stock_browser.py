"""Provider website adapters: visible controls only, never private endpoints or preview URLs."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid
from urllib.parse import urljoin,urlsplit


class StockError(ValueError):pass


def safe_item(url,kind):
    value=urlsplit(url)
    expected='/stock-footage/clip/' if kind=='broll' else '/royalty-free-music/song/'
    return value.scheme=='https' and value.hostname=='artlist.io' and value.path.startswith(expected) and not value.query and not value.fragment


def ensure_session(page,provider):
    host=urlsplit(page.url).hostname or ''
    allowed=('artlist.io',) if provider=='artlist' else ('app.envato.com','elements.envato.com')
    if host not in allowed:raise StockError('กรุณาล็อกอินให้เสร็จบนเว็บผู้ให้บริการ แล้วกดตรวจบัญชี')
    text=page.locator('body').inner_text(timeout=12000)
    if re.search(r'verify you are human|checking your browser|complete the captcha',text,re.I):raise StockError('เว็บขอให้ยืนยันตัวตน กรุณาทำในหน้าต่างบัญชีด้วยตัวเอง')
    if page.get_by_role('button',name=re.compile(r'^(Sign In|Log In|Sign in|Log in)$')).count():raise StockError('ยังไม่ได้ล็อกอิน กรุณาเข้าบัญชีของคุณในหน้าต่างเว็บก่อน')
    positive=page.get_by_role('button',name=re.compile(r'account|profile|user menu',re.I)).count()+page.get_by_role('link',name=re.compile(r'account|my downloads|sign out|log out',re.I)).count()
    if not positive:raise StockError('ยังยืนยันสถานะบัญชีไม่ได้ กรุณาเปิดหน้าบัญชีของคุณแล้วตรวจอีกครั้ง')


def rank_items(rows,query,kind):
    terms=set(re.findall(r'[a-z]{3,}',query.lower()))-{'footage','video','music','stock','with','and','the'}
    candidates=[];seen=set()
    for row in rows:
        url=urljoin('https://artlist.io',str(row.get('href','')))
        if not safe_item(url,kind) or url in seen:continue
        seen.add(url);title=str(row.get('title','')).strip()[:240]
        matches=terms & set(re.findall(r'[a-z]{3,}',title.lower()))
        if not matches:continue
        candidates.append(dict(url=url,title=title,score=len(matches)/max(1,len(terms))))
    return sorted(candidates,key=lambda r:-r['score'])


def verify_file(path,kind):
    from . import core_engine as CE
    p=Path(path)
    allowed={'.mp4','.mov','.webm'} if kind=='broll' else {'.wav','.mp3','.m4a','.aiff'}
    if p.suffix.lower() not in allowed or not p.is_file() or not 1024<=p.stat().st_size<=350*1024*1024:raise StockError('ไฟล์ที่ดาวน์โหลดไม่ใช่สื่อที่รองรับหรือมีขนาดเกิน 350 MB')
    if re.search(r'preview|watermark|sample',p.name,re.I):raise StockError('พบชื่อไฟล์ตัวอย่าง/ลายน้ำ จึงไม่นำเข้าโปรเจกต์')
    duration=_duration(p)
    if not duration or duration<.5:raise StockError('อ่านไฟล์สื่อจริงไม่ได้ จึงไม่นำเข้าโปรเจกต์')
    digest=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
    return dict(duration=duration,sha256=digest.hexdigest(),size=p.stat().st_size)


def _duration(path):
    from . import core_engine as CE
    binary=CE.ac_ffprobe_bin()
    if not binary:raise StockError('ไม่พบตัวอ่านไฟล์สื่อ กรุณาตรวจเครื่องมือของแอป')
    try:
        result=subprocess.run([binary,'-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],capture_output=True,text=True,timeout=20)
        return float(result.stdout.strip()) if result.returncode==0 else 0
    except subprocess.TimeoutExpired as exc:raise StockError('ตัวอ่านไฟล์สื่อไม่ตอบกลับภายใน 20 วินาที กรุณาตรวจไฟล์ที่ดาวน์โหลด') from exc
    except (ValueError,OSError):return 0


def _same(path,digest):
    try:return json.loads(path.read_bytes()).get('sha256')==digest
    except (OSError,ValueError):return False
