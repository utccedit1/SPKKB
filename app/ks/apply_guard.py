"""Validate the displayed source and commit subtitle generation with durable undo."""
import hashlib
import json
import os
import threading
from pathlib import Path
from . import event_timeline as T

_locks = {}
_mutex = threading.Lock()

def project_lock(proj):
    with _mutex:
        return _locks.setdefault(os.path.realpath(proj), threading.RLock())

def prepare(proj, cfg):
    T.ensure_closed()
    root = Path(proj)
    live = (root/'draft_info.json').read_bytes()
    digest = hashlib.sha1(live).hexdigest()
    if not cfg.get('state_hash') or not cfg.get('source_hash'):
        raise ValueError('กรุณาโหลดซับล่าสุดก่อนสร้างซับหรือ Super Text')
    if cfg.get('source_project') and os.path.realpath(cfg['source_project']) != os.path.realpath(proj):
        raise ValueError('โปรเจกต์เปลี่ยนแล้ว กรุณาโหลดซับล่าสุดก่อนสร้าง')
    if cfg['source_hash'] != digest:
        raise ValueError('ไทม์ไลน์เปลี่ยนหลังโหลดซับ ยังไม่ได้แก้ไฟล์ กรุณาโหลดซับล่าสุดและตรวจรายการอีกครั้ง')
    try:
        state = json.loads((root/'.spinworld_state.json').read_bytes())
    except (OSError, ValueError):
        state = {}
    original = root/'draft_info_original.json'
    baseline = original.read_bytes() if original.is_file() and state.get('output_hash') == digest else live
    if cfg['state_hash'] != hashlib.sha1(baseline).hexdigest():
        raise ValueError('รายการซับที่เลือกไม่ตรงกับต้นฉบับล่าสุด กรุณาโหลดซับใหม่และตรวจรายการ')
    parent = T.target_path(proj, '__project_draft_info.json')
    parent_raw = parent.read_bytes() if parent is not None and parent.is_file() else None
    if parent_raw is not None and json.loads(parent_raw).get('id') != json.loads(live).get('id'):
        raise ValueError('ไทม์ไลน์นี้ไม่ใช่ไทม์ไลน์หลักล่าสุด กรุณาเลือกไทม์ไลน์หลักก่อนสร้าง')
    return {'live':live, 'baseline':baseline, 'parent':parent_raw}

def commit(proj, prepared, draft):
    root = Path(proj)
    parent = T.target_path(proj, '__project_draft_info.json')
    def check():
        T.ensure_closed()
        if (root/'draft_info.json').read_bytes() != prepared['live']:
            raise ValueError('ไทม์ไลน์เปลี่ยนระหว่างสร้าง ยังไม่ได้เขียนผล กรุณาโหลดซับใหม่')
        if prepared['parent'] is not None and parent.read_bytes() != prepared['parent']:
            raise ValueError('ไทม์ไลน์หลักเปลี่ยนระหว่างสร้าง ยังไม่ได้เขียนผล กรุณาโหลดซับใหม่')
    check()
    from .event_clip import progress
    progress(message='กำลังสำรองก่อนสร้างซับ / Super Text', commit_started=True)
    backup = T.checkpoint(proj, 'before_apply')
    old = T.read_checkpoint(proj, backup.name)
    if old['draft_info.json'] != prepared['live']:
        raise ValueError('ไทม์ไลน์เปลี่ยนระหว่างสำรอง ยังไม่ได้เขียนผล กรุณาโหลดซับใหม่')
    check()
    from . import core_engine as C
    C.snapshot(proj, label='before_apply')
    output = json.dumps(draft, ensure_ascii=False).encode('utf-8')
    state = json.loads(old['.spinworld_state.json'] or b'{}')
    state['output_hash'] = hashlib.sha1(output).hexdigest()
    updates = {'draft_info.json':output, 'draft_info_original.json':prepared['baseline'],
               '.spinworld_state.json':json.dumps(state).encode('utf-8')}
    if old['draft_info_backup.json'] is None:
        updates['draft_info_backup.json'] = prepared['live']
    updates.update(T.mirror_updates(old, output))
    check()
    T.assert_unchanged(proj, old, updates)
    try:
        T.replace_files(proj, updates)
    except Exception:
        T.replace_files(proj, {name:old[name] for name in updates})
        raise
    return backup.name
