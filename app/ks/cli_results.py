"""Durable completed outputs, scoped by account/project with original fingerprints."""
import json
from pathlib import Path
import time
import uuid
from . import job_store
from .cli_lab_nested import drafts


def remember(owner, project, folder, source_hash, operation):
    from .cli_lab_commit import digest
    folder = Path(folder).resolve()
    raw = (folder/'draft_info.json').read_bytes()
    media = {}
    media_draft=json.loads(raw)
    if operation=='broll_only':
        from .cli_lab_story import resolve_media_paths
        media_draft=resolve_media_paths(media_draft,project)
    for node in drafts(media_draft):
        for kind in ('videos', 'audios'):
            for material in node.get('materials', {}).get(kind, []):
                if material.get('path'):
                    p = Path(material['path'])
                    stat = p.stat()
                    media[str(p)] = [stat.st_size, stat.st_mtime_ns]
    token = uuid.uuid4().hex
    job_store.save('results', token, dict(owner=owner, project=str(Path(project).resolve()),
        result=str(folder), source_hash=source_hash, output_hash=digest(raw), media=media,
        created=time.time(), operation=operation, state='ready'))
    return token


def listing(owner, project):
    project = str(Path(project).resolve())
    # Adopt previous-version import receipts without refreshing their fingerprints.
    for token, ticket in job_store.records(owner, 'installs'):
        if ticket.get('project') != project or ticket.get('result_id'): continue
        legacy = 'legacy'+token
        if job_store.load(owner, 'results', legacy) is None:
            job_store.save('results', legacy, dict(ticket, state='ready', operation='apply'))
    rows = [dict(result_id=token, destination=r['result'], created=r['created'], operation=r.get('operation','apply'))
            for token, r in job_store.records(owner, 'results')
            if r.get('project') == project and r.get('state') == 'ready']
    return dict(ok=True, results=sorted(rows, key=lambda r:r['created'], reverse=True)[:30])


def review(owner, project, token):
    from . import cli_lab_commit as C
    record = job_store.load(owner, 'results', token)
    if not record or record.get('project') != str(Path(project).resolve()) or record.get('state') != 'ready':
        raise ValueError('ไม่พบผลที่รอนำเข้าของผู้ใช้และโปรเจกต์นี้')
    return C.preview(owner, project, record['result'], expected=record, result_id=token)


def imported(owner, project, folder):
    project, folder = str(Path(project).resolve()), str(Path(folder).resolve())
    for token, record in job_store.records(owner, 'results'):
        if record.get('project') == project and record.get('result') == folder and record.get('state') == 'ready':
            record.update(state='imported', imported=time.time())
            job_store.save('results', token, record)
