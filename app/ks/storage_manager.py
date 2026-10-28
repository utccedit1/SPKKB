"""Preview and reversible cleanup of old developer builds; never delete user media."""
import os
from pathlib import Path
import re
import threading
import time
import uuid

_lock=threading.RLock()
_tickets={}
BUILD_PATTERN=r'(?:dist|build)-(\d+\.\d+\.\d+)(?:-final)?'
KEEP_VERSIONS=5


def build_root():
    from .updater import _get_app_bundle_path
    bundle=_get_app_bundle_path()
    if bundle:
        parent=Path(bundle).resolve().parent
        # Developer release folders sit beside build-*; installed apps do not.
        return parent.parent if re.fullmatch(r'dist-\d+\.\d+\.\d+(?:-final)?',parent.name) else parent
    return Path(__file__).resolve().parents[1]


def _reference_roots():
    from .ce_config import load_config
    roots=[Path.home()/'Movies/CapCut/User Data/Projects/com.lveditor.draft']
    for value in load_config().get('recent_projects',[]):
        if isinstance(value,str):roots.append(Path(value))
    return [p for p in roots if p.exists()]


def _referenced(paths, roots):
    """Fail closed if a bounded scan cannot establish that old builds are unused."""
    import json
    needles={str(p.resolve()):p for p in paths};found=set();deadline=time.monotonic()+15;count=0
    def strings(value):
        if isinstance(value,str):yield value
        elif isinstance(value,dict):
            for item in value.values():yield from strings(item)
        elif isinstance(value,list):
            for item in value:yield from strings(item)
    for root in roots:
        for folder,dirs,files in os.walk(root,followlinks=False,onerror=lambda e:(_ for _ in ()).throw(e)):
            dirs[:]=[d for d in dirs if not (Path(folder)/d).is_symlink()]
            count+=len(files)
            if count>50000 or time.monotonic()>deadline:raise ValueError('ตรวจการอ้างอิงไม่ครบ กรุณาตรวจโปรเจกต์ก่อนเคลียร์พื้นที่')
            for name in files:
                if not name.endswith('.json'):continue
                path=Path(folder)/name
                if path.is_symlink():continue
                if path.stat().st_size>64*1024*1024:raise ValueError('ไฟล์โปรเจกต์ใหญ่เกินขอบเขตตรวจอัตโนมัติ ยังไม่ย้ายไฟล์เก่า')
                try:data=json.loads(path.read_bytes())
                except (ValueError,UnicodeError):
                    if name.startswith('draft'):raise ValueError('อ่านโปรเจกต์เพื่อตรวจการอ้างอิงไม่ได้: '+str(path)+' · ยังไม่ย้ายไฟล์เก่า')
                    continue
                for value in strings(data):
                    normalized=str(Path(value).resolve()) if value.startswith('/') else value
                    for needle in needles:
                        if needle in normalized or needle in value:found.add(needle)
    return found


def _size(root):
    total=0
    for folder,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if not (Path(folder)/d).is_symlink()]
        for name in files:
            path=Path(folder)/name
            if not path.is_symlink():total+=path.stat().st_size
    return total


def _trash_root(root):
    import hashlib
    return Path.home()/'.Trash'/'Chuaydai-builds'/hashlib.sha256(str(root).encode()).hexdigest()[:16]


def _running_bundles():
    """Use process executable paths; fail closed when inspection is unavailable."""
    import subprocess
    import sys
    from .updater import _get_app_bundle_path
    current = _get_app_bundle_path()
    bundles = {Path(current).resolve()} if current else set()
    if sys.platform == 'darwin':
        try:run = subprocess.run(['/bin/ps','-axo','comm='],capture_output=True,text=True,timeout=10)
        except (OSError,subprocess.SubprocessError) as exc:
            raise ValueError('ตรวจแอปที่กำลังใช้งานไม่ได้ ยังไม่ย้ายรุ่นเก่า') from exc
        if run.returncode:raise ValueError('ตรวจแอปที่กำลังใช้งานไม่ได้ ยังไม่ย้ายรุ่นเก่า')
        for line in run.stdout.splitlines():
            value=line.strip()
            if '.app/Contents/MacOS/' in value:
                bundles.add(Path(value.split('.app/Contents/MacOS/',1)[0]+'.app').resolve())
    return bundles


def _protected_running(path, bundles):
    return any(bundle.is_relative_to(path) for bundle in bundles)


def preview(owner, root=None, reference_roots=None):
    from .updater import CURRENT_VERSION, _parse_version
    root=Path(root or build_root()).resolve()
    groups=[]
    for path in root.iterdir():
        match=re.fullmatch(BUILD_PATTERN,path.name)
        if match and path.is_dir() and not path.is_symlink():groups.append((match[1],path))
    versions=sorted({v for v,p in groups},key=_parse_version,reverse=True)
    keep=set(versions[:KEEP_VERSIONS])|{CURRENT_VERSION}
    running=_running_bundles()
    scan_roots=[Path(p) for p in (reference_roots if reference_roots is not None else _reference_roots())]
    referenced=_referenced([p for v,p in groups if v not in keep],scan_roots)
    rows=[];protected=[]
    for version,path in groups:
        if version in keep:continue
        if str(path) in referenced or _protected_running(path,running):protected.append(path.name);continue
        stamp=path.stat()
        rows.append(dict(path=str(path),name=path.name,size=_size(path),inode=stamp.st_ino))
    token=uuid.uuid4().hex
    with _lock:_tickets[token]=dict(owner=owner,root=str(root),created=time.time(),rows=rows,state='preview',reference_roots=[str(p) for p in scan_roots])
    return dict(ok=True,cleanup_id=token,files=rows,protected=protected,total_bytes=sum(r['size'] for r in rows),
                note='ย้ายเข้า Trash แบบกู้คืนได้ ยังไม่คืนพื้นที่ดิสก์จนกว่าคุณจะล้าง Trash ด้วยตนเอง ตรวจเฉพาะ build/dist รุ่นเก่า เก็บ 5 รุ่นล่าสุด รุ่นปัจจุบัน และรุ่นที่กำลังใช้งาน สื่อ โปรเจกต์ audits และ backup ทั้งหมดคงอยู่')


def move(owner, token):
    with _lock:
        ticket=_tickets.get(token)
        if not ticket or ticket['owner']!=owner or time.time()-ticket['created']>600 or ticket['state']!='preview':
            raise ValueError('แผนเคลียร์พื้นที่หมดอายุ กรุณาตรวจใหม่')
        root=Path(ticket['root']);trash=_trash_root(root)/token
        if _referenced([Path(row['path']) for row in ticket['rows']],[Path(p) for p in ticket['reference_roots']]):
            raise ValueError('มีโปรเจกต์อ้างอิงไฟล์เก่าเพิ่มขึ้น กรุณาตรวจพื้นที่ใหม่')
        running=_running_bundles()
        for row in ticket['rows']:
            path=Path(row['path'])
            if _protected_running(path,running):raise ValueError('รุ่นเก่านี้กำลังเปิดใช้งาน ยังไม่ย้ายไฟล์')
            if path.parent!=root or path.is_symlink() or not path.is_dir() or path.stat().st_ino!=row['inode']:
                raise ValueError('ไฟล์เปลี่ยนหลังตรวจ กรุณาตรวจพื้นที่ใหม่')
        trash.mkdir(parents=True,exist_ok=False)
        from .ce_config import _atomic_json
        # Persist the undo manifest before any move.
        _atomic_json(str(trash/'manifest.json'),ticket)
        moved=[]
        try:
            for row in ticket['rows']:
                path=Path(row['path']);path.rename(trash/path.name);moved.append(path.name)
        except Exception:
            for name in reversed(moved):(trash/name).rename(root/name)
            raise
        ticket['state']='moved'
        return dict(ok=True,cleanup_id=token,message='ย้ายรุ่นเก่าเข้า Trash แล้ว ย้อนคืนได้ด้วยปุ่มกู้คืนไฟล์เก่า',bytes_moved=sum(r['size'] for r in ticket['rows']))


def restore(owner, token, root=None):
    import json
    if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{32}',token):raise ValueError('รหัสกู้คืนไม่ถูกต้อง')
    root=Path(root or build_root()).resolve();trash=_trash_root(root)/token
    if not (trash/'manifest.json').is_file():trash=root/'.cleanup_trash'/token
    ticket=json.loads((trash/'manifest.json').read_bytes())
    if ticket['owner']!=owner or ticket['root']!=str(root):raise ValueError('รายการกู้คืนเป็นของผู้ใช้อื่น')
    for row in ticket['rows']:
        name=row['name']
        if not re.fullmatch(BUILD_PATTERN,name):raise ValueError('รายการกู้คืนไม่ถูกต้อง')
        if (root/name).exists():raise ValueError('มีไฟล์ชื่อเดิมอยู่แล้ว ยังไม่ได้กู้คืนทับ')
        if not (trash/name).is_dir() or (trash/name).is_symlink():raise ValueError('ไม่พบไฟล์กู้คืน')
    restored=[]
    try:
        for row in ticket['rows']:
            (trash/row['name']).rename(root/row['name']);restored.append(row['name'])
    except Exception:
        # Keep the same undo ticket usable if a later rename fails.
        for name in reversed(restored):(root/name).rename(trash/name)
        raise
    return dict(ok=True,message='กู้คืนไฟล์เก่าครบแล้ว')
