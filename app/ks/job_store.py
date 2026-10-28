"""Private per-owner job receipts; an interrupted process never silently resumes writes."""
import hashlib
import json
import os
from pathlib import Path
import uuid

INSTANCE = uuid.uuid4().hex


def _path(owner, family, token):
    if family not in ('cli','event','stock','plans','installs','results') or not isinstance(token,str) or not token.isalnum() or len(token)>80:
        raise ValueError('รหัสงานไม่ถูกต้อง')
    if not owner:raise ValueError('ไม่พบเจ้าของงาน')
    from . import ce_config as C
    return Path(os.environ.get('KS_JOB_STATE_DIR', str(Path(C.CONFIG_DIR)/'job_receipts')))/hashlib.sha256(owner.encode()).hexdigest()/family/(token+'.json')


def save(family, token, job):
    from .ce_config import _atomic_json
    record=dict(job, instance=INSTANCE)
    _atomic_json(str(_path(record['owner'],family,token)),record)


def load(owner, family, token):
    path=_path(owner,family,token)
    if not path.is_file():return None
    record=json.loads(path.read_bytes())
    if not isinstance(record, dict):raise ValueError('รายการงานเสียหาย')
    if record.get('owner')!=owner:raise ValueError('เจ้าของงานไม่ตรงกัน')
    if record.get('instance')!=INSTANCE and record.get('state') in ('queued','running','cancelling'):
        record.update(state='failed',error='แอปปิดระหว่างทำงาน กรุณาเริ่มใหม่ งานที่บันทึกไม่ครบจะไม่ถูกใช้กับโปรเจกต์',message='งานขัดจังหวะ กรุณาเริ่มใหม่')
    return record


def forget(owner,family,token):
    _path(owner,family,token).unlink(missing_ok=True)


def records(owner, family):
    """Enumerate only this owner's receipts; damaged individual files are skipped."""
    folder = _path(owner, family, 'index').parent
    for path in folder.glob('*.json'):
        try:
            record = load(owner, family, path.stem)
            if record is not None: yield path.stem, record
        except (OSError, ValueError, TypeError):
            continue
