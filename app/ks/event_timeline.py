"""Transactional edits to the selected draft with durable undo checkpoints."""
import hashlib
import base64
import threading
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid
from . import event_clip as E

FILES = ('draft_info.json', 'draft_content.json', 'draft_meta_info.json',
         'draft_info_original.json', 'draft_info_backup.json', '.spinworld_state.json',
         'draft_info.json.bak', '__project_draft_info.json', '__project_draft_info.json.bak', '__project_draft_meta_info.json')
EXTRA_MIRRORS = ('template-2.tmp', '__project_template-2.tmp', '__project_draft_content.json')
FILES += EXTRA_MIRRORS
BACKUPS = '.event_timeline_backups'


def target_path(proj, name):
    root = Path(proj)
    if name.startswith('__project_'):
        if root.parent.name != 'Timelines':
            return None
        # The project root mirrors only the active timeline, never every timeline.
        selected = json.loads((root/'draft_info.json').read_bytes())
        main = root.parent.parent/'draft_info.json'
        if not main.is_file():
            return None
        parent = json.loads(main.read_bytes())
        if not selected.get('id') or parent.get('id') != selected['id']:
            return None
        return root.parent.parent / name[len('__project_'):]
    return root/name


MIRRORS = ('draft_info.json', 'draft_content.json', 'draft_info.json.bak',
           'template-2.tmp', '__project_draft_info.json', '__project_draft_content.json',
           '__project_draft_info.json.bak', '__project_template-2.tmp')


def mirror_updates(before, output):
    """Update existing active-timeline mirrors, never pristine/undo snapshots."""
    identity = json.loads(before['draft_info.json']).get('id')
    edited = json.loads(output)
    if edited.get('id') != identity:
        raise ValueError('รหัสไทม์ไลน์ผลลัพธ์เปลี่ยน ยังไม่ได้บันทึก')
    updates = {}
    for name in MIRRORS:
        raw = before.get(name)
        if raw is None: continue
        try: draft = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError('ไฟล์ไทม์ไลน์ประกอบอ่านไม่ได้: '+name)
        if not isinstance(draft, dict) or draft.get('id') != identity or not isinstance(draft.get('tracks'), list):
            raise ValueError('ไฟล์ไทม์ไลน์ประกอบไม่ตรงกัน: '+name)
        updates[name] = output
    return updates


def assert_unchanged(proj, before, names):
    for name in names:
        path = target_path(proj, name)
        live = path.read_bytes() if path is not None and path.is_file() else None
        if live != before.get(name):
            raise ValueError('ไฟล์ไทม์ไลน์เปลี่ยนก่อนบันทึก: '+name)


def ensure_closed(home_confirmed=False):
    # Use exactly the same inspection as the visible CapCut diagnostic.
    from .capcut_session import status
    report = status()
    state = report.get('state', 'unknown')
    if state in ('closed', 'unsupported'):return
    if state == 'editor' or any(p.get('state') == 'editor' for p in report.get('processes', [])):
        raise ValueError('กรุณาบันทึกแล้วออกจากหน้าโปรเจกต์กลับหน้าหลัก CapCut ก่อนจัดซับ/ตัด/กู้คืน เปิดแอปค้างไว้ได้')
    if report.get('ok') and state == 'home':return
    if home_confirmed is True:return
    if report.get('trusted') is False:
        raise ValueError('macOS ยังไม่อนุญาตไฟล์แอปช่วยด้วยจ้าปัจจุบัน แม้สวิตช์สิทธิ์เปิดอยู่: ไป Privacy & Security > Accessibility ลบรายการช่วยด้วยจ้าเดิม แล้วเพิ่มแอปที่ติดตั้งใน Applications ใหม่ จากนั้นเปิดสิทธิ์และเริ่มช่วยด้วยจ้าใหม่')
    raise ValueError('ยังตรวจไม่พบหน้าหลัก CapCut กรุณาบันทึกแล้วออกจากโปรเจกต์ หากกลับหน้าหลักแล้วแต่ยังแจ้งเตือน ให้ตรวจสิทธิ์การช่วยการเข้าถึงของโปรแกรม')


def _sync_directory(path):
    import errno
    descriptor=os.open(str(path),os.O_RDONLY)
    try:
        try:os.fsync(descriptor)
        except OSError as exc:
            if exc.errno not in (errno.EINVAL,errno.ENOTSUP):raise
    finally:os.close(descriptor)


def atomic_write(path, data):
    fd, tmp = tempfile.mkstemp(prefix='.event_write_', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        _sync_directory(path.parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def checkpoint(proj, label):
    root = Path(proj)
    folder = root / BACKUPS / (time.strftime('%Y%m%d_%H%M%S')+'_'+label+'_'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    manifest = {'created':time.time(), 'label':label, 'project':str(root.resolve()), 'files':{}}
    for name in FILES:
        path = target_path(proj, name)
        if path is not None and path.is_file():
            data=path.read_bytes()
            atomic_write(folder/name, data)
            manifest['files'][name]=hashlib.sha256(data).hexdigest()
        else:
            manifest['files'][name]=None
    atomic_write(folder/'manifest.json',json.dumps(manifest,ensure_ascii=False).encode())
    return folder


def read_checkpoint(proj, name):
    if not isinstance(name,str) or not name or Path(name).name != name:
        raise ValueError('ชื่อ backup ไม่ถูกต้อง')
    folder=Path(proj)/BACKUPS/name
    manifest=json.loads((folder/'manifest.json').read_text())
    if manifest.get('project') != str(Path(proj).resolve()):
        raise ValueError('backup เป็นของโปรเจกต์อื่น')
    output={}
    for filename in FILES:
        if filename not in manifest['files']:
            if filename in EXTRA_MIRRORS:
                continue  # Older checkpoints predate these mirrors; don't remove unrecorded files.
            raise ValueError('backup ไม่ครบ')
        digest=manifest['files'][filename]
        data=(folder/filename).read_bytes() if digest else None
        if data is not None and hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError('backup เสียหาย ยังไม่แก้ไทม์ไลน์')
        output[filename]=data
    # Older checkpoints may contain a different timeline's root mirror.
    mirror = output.get('__project_draft_info.json')
    selected = json.loads(output['draft_info.json'])
    if mirror is not None and json.loads(mirror).get('id') != selected.get('id'):
        for filename in FILES:
            if filename.startswith('__project_'):
                output[filename] = None
    return output


_transaction_lock = threading.RLock()
JOURNAL = '.ks_pending_transaction.json'


def _digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def recover_pending(proj):
    """Roll back an interrupted commit only if every file still matches its journal."""
    with _transaction_lock:
        journal = Path(proj)/JOURNAL
        if not journal.is_file(): return False
        record = json.loads(journal.read_bytes())
        if record.get('project') != str(Path(proj).resolve()):
            raise ValueError('รายการกู้คืนเป็นของโปรเจกต์อื่น')
        entries = record.get('entries', {})
        if not entries or any(name not in FILES for name in entries):
            raise ValueError('รายการกู้คืนไม่ถูกต้อง')
        targets = {name: target_path(proj, name) for name in entries}
        decoded = {}
        for name, entry in entries.items():
            target = targets[name]
            if target is None: raise ValueError('ขอบเขตไฟล์กู้คืนเปลี่ยน กรุณาตรวจโปรเจกต์')
            before = base64.b64decode(entry['before'], validate=True) if entry['before'] is not None else None
            if _digest(before) != entry['before_hash']: raise ValueError('ข้อมูลกู้คืนเสียหาย')
            current = target.read_bytes() if target.is_file() else None
            if _digest(current) not in (entry['before_hash'], entry['after_hash']):
                raise ValueError('โปรเจกต์เปลี่ยนหลังการบันทึกขัดข้อง จึงยังไม่กู้คืนทับข้อมูลใหม่')
            decoded[name] = before
        for name, before in decoded.items():
            target = targets[name]
            if before is None:
                if target.exists(): target.unlink()
            else: atomic_write(target, before)
        journal.unlink()
        _sync_directory(journal.parent)
        return True


def replace_files(proj, files):
    # Durable before-images survive process termination between mirror writes.
    with _transaction_lock:
        recover_pending(proj)
        if any(name not in FILES for name in files): raise ValueError('ชื่อไฟล์ไทม์ไลน์ไม่ถูกต้อง')
        targets = {name: target_path(proj, name) for name in files}
        entries = {}
        for name, data in files.items():
            path = targets[name]
            if path is None: continue
            before = path.read_bytes() if path.is_file() else None
            entries[name] = dict(before=base64.b64encode(before).decode() if before is not None else None,
                                 before_hash=_digest(before), after_hash=_digest(data))
        if not entries: return
        journal = Path(proj)/JOURNAL
        atomic_write(journal, json.dumps(dict(project=str(Path(proj).resolve()),entries=entries)).encode())
        try:
            for name, data in files.items():
                path = targets[name]
                if path is None: continue
                if data is None:
                    if path.exists(): path.unlink()
                else: atomic_write(path, data)
        except Exception:
            recover_pending(proj)
            raise
        journal.unlink()
        _sync_directory(journal.parent)


def list_backups(proj):
    rows=[]
    root=Path(proj)/BACKUPS
    if root.is_dir():
        for folder in root.iterdir():
            try:
                m=json.loads((folder/'manifest.json').read_text())
                rows.append({'name':folder.name,'created':m['created'],'label':m['label']})
            except (OSError, ValueError, KeyError):pass
    return {'ok':True,'backups':sorted(rows,key=lambda r:r['created'],reverse=True)}


def apply(proj,cfg):
    ensure_closed()
    E.progress(completed=0,total=3,message='กำลังตรวจไทม์ไลน์ล่าสุด')
    if cfg.get('source_project') and os.path.realpath(cfg['source_project']) != os.path.realpath(proj):
        raise ValueError('แผนนี้เป็นของโปรเจกต์อื่น กรุณาเลือกโปรเจกต์เดิมหรือวางแผนใหม่')
    draft,_,digest=E.transcript(proj)
    if cfg.get('source_hash') != digest:
        raise ValueError('ไทม์ไลน์ล่าสุดเปลี่ยนจากตอนวางแผน กรุณาวางแผนใหม่ก่อนตัด')
    duration=max((int(s.get('target_timerange',{}).get('start',0))+int(s.get('target_timerange',{}).get('duration',0))
                  for t in draft.get('tracks',[]) for s in t.get('segments',[])),default=0)
    windows=[]
    import math
    for a,b in cfg.get('segments',[]):
        a,b=float(a),float(b)
        if not math.isfinite(a) or not math.isfinite(b) or not 0<=a<b<=duration/1e6:
            raise ValueError('ช่วงตัดอยู่นอกไทม์ไลน์')
        windows.append((round(a*1e6),round(b*1e6)))
    if not windows:raise ValueError('ไม่มีช่วงให้ตัด')
    main = target_path(proj, '__project_draft_info.json')
    if main is not None and main.is_file():
        parent_draft = json.loads(main.read_bytes())
        if parent_draft.get('id') != draft.get('id'):
            raise ValueError('ไทม์ไลน์ที่เลือกไม่ใช่ไทม์ไลน์หลักล่าสุด กรุณาเลือกไทม์ไลน์หลักก่อนตัด')
    cut=E.CE.ac_cut_timeline(draft,windows)
    for track in cut.get('tracks',[]):
        for seg in track.get('segments',[]):
            if any(group.get('keyframe_list') for group in seg.get('common_keyframes',[])):
                raise ValueError('พบโมชั่นคีย์เฟรมที่ยังรักษาจังหวะหลังตัดไม่ได้ กรุณาใช้ไทม์ไลน์ฟุตเทจกับ Auto Caption ก่อน')
    cut['duration']=sum(b-a for a,b in E.CE.ac_normalize_windows(windows))
    E.progress(completed=1,total=3,message='กำลังบันทึก backup ก่อนตัดจริง',commit_started=True)
    backup=checkpoint(proj,'before_cut')
    old=read_checkpoint(proj,backup.name)
    if hashlib.sha256(old['draft_info.json']).hexdigest()!=digest or E.transcript(proj)[2]!=digest:
        raise ValueError('ไทม์ไลน์เปลี่ยนระหว่างสำรอง กรุณาวางแผนใหม่ ยังไม่ได้ตัด')
    updated=dict(old)
    data=json.dumps(cut,ensure_ascii=False).encode('utf-8')
    updated.update(mirror_updates(old,data))
    for name in ('draft_meta_info.json','__project_draft_meta_info.json'):
        if old[name] is not None:
            meta=json.loads(old[name])
            meta.update(tm_duration=cut['duration'],tm_draft_modified=int(time.time()*1e6))
            updated[name]=json.dumps(meta,ensure_ascii=False).encode('utf-8')
    # Remove cached pristine caption state from the previous timeline; undo restores it.
    for name in ('draft_info_original.json','draft_info_backup.json','.spinworld_state.json'):
        updated[name]=None
    ensure_closed()
    E.progress(completed=2,total=3,message='backup เสร็จแล้ว กำลังตัดไทม์ไลน์โปรเจกต์เดิม')
    assert_unchanged(proj, old, updated)
    try:
        replace_files(proj,updated)
    except Exception:
        replace_files(proj,old)
        raise
    return {'ok':True,'inplace':True,'project':proj,'backup_name':backup.name,'backup':str(backup),
            'duration':cut['duration']/1e6,'message':'ตัดไทม์ไลน์โปรเจกต์เดิมแล้ว เปิด CapCut และเปิดโปรเจกต์เดิมเพื่อตรวจ',
            'backups':list_backups(proj)['backups']}


def restore(proj,cfg):
    from .unified_history import restore as restore_history
    result = restore_history(proj, dict(cfg, id='checkpoint:' + str(cfg.get('backup_name',''))))
    result.update(inplace=True, restored=cfg.get('backup_name'), backups=list_backups(proj)['backups'])
    return result
