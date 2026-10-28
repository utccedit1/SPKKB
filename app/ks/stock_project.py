"""Per-account/project stock storage, separate from browser authentication."""
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


def project_key(project):
    path=Path(project).expanduser().resolve()
    if path.parent.name=='Timelines':path=path.parent.parent
    return path


def settings(owner,project,folder=None):
    from .stock_accounts import user_root
    project=project_key(project)
    key=hashlib.sha256(str(project).encode()).hexdigest()
    record=user_root(owner)/'project_storage'/f'{key}.json'
    if folder is not None:
        if not isinstance(folder,str) or '\x00' in folder:raise ValueError('ตำแหน่งโฟลเดอร์ไม่ถูกต้อง')
        if folder.strip():
            chosen=Path(folder).expanduser()
            if not chosen.is_absolute() or not chosen.is_dir():raise ValueError('กรุณาเลือกโฟลเดอร์ที่มีอยู่จริง')
            folder=str(chosen.resolve())
        else:folder=''
        record.parent.mkdir(parents=True,exist_ok=True)
        from .ce_config import _atomic_json
        _atomic_json(str(record),dict(folder=folder))
    try:chosen=json.loads(record.read_bytes()).get('folder','')
    except (OSError,ValueError):chosen=''
    # A shared chosen base still gets a distinct directory for each project.
    name=re.sub(r'[^\w\- .ก-๙]','_',project.name)[:80] or 'Project'
    destination=Path(chosen)/(name+'-'+key[:8]) if chosen else project/'ช่วยด้วยจ้า สื่อ'
    return dict(ok=True,folder=chosen,destination=str(destination),project_name=project.name)


def store(source,destination,category,title='media'):
    """Content-addressed copy; never replace an unrelated existing file."""
    source=Path(source);root=Path(destination)/category
    root.mkdir(parents=True,exist_ok=True)
    def sha(path):
        with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()
    digest=sha(source)
    title=re.sub(r'[^\w\- .ก-๙]','_',title).strip(' .')[:64] or 'media'
    target=root/(title+'-'+digest[:16]+source.suffix.lower())
    if target.exists():
        if sha(target)!=digest:raise ValueError('ไฟล์ปลายทางถูกแก้ไข กรุณาเลือกโฟลเดอร์ใหม่')
        return str(target)
    fd,temporary=tempfile.mkstemp(prefix='.stock-',dir=root);os.close(fd)
    try:
        shutil.copyfile(source,temporary)
        # Atomic creation without overwriting a concurrent user file.
        try:os.link(temporary,target)
        except OSError as exc:
            if isinstance(exc,FileExistsError):
                if sha(target)!=digest:raise ValueError('ไฟล์ปลายทางชนกัน กรุณาลองใหม่')
            elif exc.errno in (errno.EPERM,errno.EOPNOTSUPP,errno.ENOSYS,errno.EXDEV):
                # exFAT/removable drives may not support hard links.
                try:handle=target.open('xb')
                except FileExistsError:
                    if sha(target)!=digest:raise ValueError('ไฟล์ปลายทางชนกัน กรุณาลองใหม่')
                else:
                    try:
                        with handle,Path(temporary).open('rb') as incoming:shutil.copyfileobj(incoming,handle)
                    except BaseException:
                        target.unlink(missing_ok=True);raise
            else:raise
    finally:Path(temporary).unlink(missing_ok=True)
    return str(target)
