"""Reviewed replacement of the selected timeline, with recoverable mirror backups."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
import uuid

from . import event_timeline as T
from .apply_guard import project_lock
from .cli_lab_nested import drafts
from . import job_store

_tickets = {}
_lock = threading.Lock()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate(draft):
    duration = draft.get('duration')
    if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0 or not isinstance(draft.get('tracks'), list):
        raise ValueError('ผลตัดต่อไม่มีไทม์ไลน์หรือความยาวที่ถูกต้อง')
    materials = {m['id'] for group in draft.get('materials', {}).values() if isinstance(group, list)
                 for m in group if isinstance(m, dict) and isinstance(m.get('id'), str)}
    ids = set()
    for track in draft['tracks']:
        for seg in track.get('segments', []):
            if not seg.get('id') or seg['id'] in ids or seg.get('material_id') not in materials:
                raise ValueError('ผลตัดต่อมี ID ซ้ำหรืออ้างวัสดุที่ไม่พบ')
            ids.add(seg['id'])
            tr = seg.get('target_timerange') or {}
            a, n = tr.get('start'), tr.get('duration')
            if any(isinstance(v, bool) or not isinstance(v, int) for v in (a, n)) or a < 0 or n <= 0 or a+n > duration+2:
                raise ValueError('ช่วงคลิปในผลตัดต่อไม่ถูกต้อง')
    if not ids:
        raise ValueError('ผลตัดต่อว่าง')


def preview(owner, project, folder, expected=None, result_id=None):
    target = Path(project).resolve()
    from .ce_project import active_project_path
    if active_project_path(target)!=str(target):
        raise ValueError('กรุณาเลือกไทม์ไลน์ที่ CapCut ใช้จริง: '+active_project_path(target))
    result = Path(str(folder)).expanduser().resolve()
    raw = (target/'draft_info.json').read_bytes()
    edited_raw = (result/'draft_info.json').read_bytes()
    edited = json.loads(edited_raw); validate(edited)
    if target == result:
        raise ValueError('กรุณาเลือกโฟลเดอร์ผลตัดต่อคนละที่กับโปรเจกต์เดิม')
    current = json.loads(raw)
    if target.parent.name == 'Timelines':
        root = target.parent.parent/'draft_info.json'
        if root.is_file() and json.loads(root.read_bytes()).get('id') != current.get('id'):
            raise ValueError('กรุณาเลือกไทม์ไลน์หลักของโปรเจกต์ก่อนแทนผล')
    broll_only = (result/'broll_only_report.json').is_file() or bool(expected and expected.get('operation')=='broll_only')
    broll_repair=(result/'broll_repair_report.json').is_file() or bool(expected and expected.get('operation')=='broll_repair')
    if broll_repair:
        from .broll_assets import validate_repair
        validate_repair(current,edited)
    media_draft=edited
    if broll_only or broll_repair:
        from .cli_lab_story import resolve_media_paths
        media_draft=resolve_media_paths(edited,target)
    stamps = {}
    for kind in ('videos', 'audios'):
        for material in (m for node in drafts(media_draft) for m in node.get('materials',{}).get(kind,[])):
            if not material.get('path'):
                continue
            path = Path(material['path'])
            if not path.is_absolute() or not path.is_file():
                raise ValueError('ไม่พบไฟล์สื่อในผลตัดต่อ: ' + str(path))
            st = path.stat(); stamps[str(path)] = (st.st_size, st.st_mtime_ns)
    if expected is not None:
        if digest(raw) != expected['source_hash'] or digest(edited_raw) != expected['output_hash'] or stamps != {k:tuple(v) for k,v in expected['media'].items()}:
            raise ValueError('ต้นฉบับ ผลตัดต่อ หรือสื่อเปลี่ยนจากตอนสร้าง ยังไม่นำเข้า กรุณาตรวจผลและต้นฉบับก่อนเตรียมนำเข้าใหม่ด้วยตนเอง')
    if broll_only:
        from .broll_auto import validate_additions
        validate_additions(current,edited)
    token = uuid.uuid4().hex
    ticket = dict(owner=owner, project=str(target), result=str(result),
        source_hash=digest(raw), output_hash=digest(edited_raw), media=stamps, created=time.time())
    if broll_only: ticket['contract'] = 'broll_only'
    if broll_repair: ticket['contract']='broll_repair'
    if result_id: ticket['result_id'] = result_id
    job_store.save('installs',token,ticket)
    with _lock:
        _tickets[token] = ticket
    return {'ok': True, 'install_id': token, 'target_project': str(target),
            'old_duration': current.get('duration', 0)/1e6, 'new_duration': edited['duration']/1e6,
            'review_notes': review_notes(result),
            'message': 'บันทึกแล้วกลับหน้าหลัก CapCut ก่อนใช้ผล ระบบจะสำรองและแทนไทม์ไลน์ในโปรเจกต์นี้'}


def review_notes(folder):
    notes=[];folder=Path(folder)
    if (folder/'broll_repair_report.json').is_file():notes.append('ตรวจไฟล์ B-roll แล้ว · ยืนยันเพื่อคัดลอกเข้าโปรเจกต์และซ่อมทะเบียนสื่อ โดยไม่เปลี่ยนรอยตัดหรือเพิ่มภาพซ้ำ')
    if (folder/'broll_only_report.json').is_file():
        report=json.loads((folder/'broll_only_report.json').read_bytes())
        notes.append(f"เพิ่มเฉพาะ B-roll {report['inserted']} ช็อต · รอยตัด ซับ เพลง เสียง โมชั่น และแทร็กเดิมคงเดิม")
    if (folder/'audio_levels_report.json').is_file():
        levels=json.loads((folder/'audio_levels_report.json').read_bytes())
        peak=levels.get('after_peak_dbfs')
        if peak is not None:notes.append(f'เสียงพูดพีก {peak:.1f} dBFS · เป้าหมาย −4 (ช่วง −6 ถึง −2)'+(' · ⚠️ เสียงต้นฉบับเบาเกินขอบเขตเพิ่มความดัง โปรดตรวจเสียงก่อนส่งออก' if levels.get('state')=='gain_limited' else ''))
    if (folder/'alignment_report.json').is_file():
        warnings=json.loads((folder/'alignment_report.json').read_bytes()).get('warnings',[])
        if warnings:notes.append(f'คงเวลาซับ CapCut {len(warnings)} ท่อนที่จับเวลารายคำไม่มั่นใจ ไม่ตัดคำในท่อนเหล่านี้ กรุณาฟังตรวจจังหวะก่อนส่งออก')
    if (folder/'caption_layout_report.json').is_file():
        estimated=json.loads((folder/'caption_layout_report.json').read_bytes())
        if estimated:notes.append(f'ซับบรรทัดเดียว: แบ่งเวลาภายในซับเดิมโดยประมาณ {len(estimated)} ท่อน กรุณาฟังตรวจจังหวะก่อนส่งออก')
    if (folder/'stock_report.json').is_file():
        rows=json.loads((folder/'stock_report.json').read_bytes())
        from .edit_report import stock_summary
        draft=json.loads((folder/'draft_info.json').read_bytes())
        notes.extend(stock_summary(rows,draft.get('duration',0)/1e6))
        supers=sum(len(t.get('segments',[])) for t in draft.get('tracks',[]) if t.get('name')=='ช่วยด้วยจ้า · Super Text')
        notes.append(f'Super Text {supers} จุด')
    return '\n'.join(notes)


def _matches_committed(ticket, target):
    expected=ticket.get('commit_updates')
    if not isinstance(expected,dict) or not expected or (target/T.JOURNAL).exists():return False
    for name, fingerprint in expected.items():
        if name not in T.FILES:return False
        path=T.target_path(str(target),name)
        if path is None:return False
        actual=digest(path.read_bytes()) if path.is_file() else None
        if actual!=fingerprint:return False
    return True


def check(owner, project, token):
    target=Path(project).resolve()
    with _lock: ticket=_tickets.get(token)
    if ticket is None:ticket=job_store.load(owner,'installs',token)
    if not ticket or ticket.get('owner')!=owner or ticket.get('project')!=str(target):
        return {'ok':True,'state':'unknown','message':'ยังยืนยันผลไม่ได้ โปรดตรวจโปรเจกต์และประวัติก่อนนำเข้าอีกครั้ง'}
    if _matches_committed(ticket,target):
        return {'ok':True,'state':'committed','message':'ตรวจพบว่าบันทึกผลในโปรเจกต์แล้ว โปรดเปิดตรวจใน CapCut'}
    return {'ok':True,'state':'unknown','message':'ยังยืนยันผลไม่ได้ โปรดตรวจโปรเจกต์และประวัติก่อนนำเข้าอีกครั้ง'}


def commit(owner, project, token, progress=lambda message: None):
    target = Path(project).resolve()
    with _lock:
        ticket = _tickets.get(token)
    if ticket is None:
        ticket = job_store.load(owner,'installs',token)
    if not ticket:
        raise ValueError('ไม่พบรายการเตรียมนำเข้า ผลตัดต่อยังอยู่ กดเตรียมนำคลิปเข้าอีกครั้ง โดยไม่ต้องตัดใหม่')
    if ticket['owner'] != owner or ticket['project'] != str(target):
        raise ValueError('รายการนำเข้านี้เป็นของผู้ใช้หรือโปรเจกต์อื่น กรุณาเลือกโปรเจกต์ที่สร้างผลนี้')
    progress('กำลังตรวจโปรเจกต์และเตรียมสำรองข้อมูล')
    with project_lock(str(target)):
        T.ensure_closed()
        from .ce_project import active_project_path
        if active_project_path(target)!=str(target):
            raise ValueError('ไทม์ไลน์ที่เลือกเปลี่ยน กรุณาตรวจผลก่อนใช้ใหม่')
        raw = (target/'draft_info.json').read_bytes()
        result = Path(ticket['result'])
        output_raw = (result/'draft_info.json').read_bytes()
        if digest(raw) != ticket['source_hash'] or digest(output_raw) != ticket['output_hash']:
            raise ValueError('โปรเจกต์หรือผลตัดต่อเปลี่ยน กรุณาตรวจผลก่อนใช้ใหม่')
        for value, stamp in ticket['media'].items():
            p = Path(value)
            if not p.is_file() or (p.stat().st_size, p.stat().st_mtime_ns) != tuple(stamp):
                raise ValueError('ไฟล์สื่อเปลี่ยน กรุณาตรวจผลก่อนใช้ใหม่')
        current = json.loads(raw); edited = json.loads(output_raw); validate(edited)
        if ticket.get('contract') == 'broll_only':
            from .broll_auto import validate_additions
            validate_additions(current,edited)
        if ticket.get('contract')=='broll_repair':
            from .broll_assets import validate_repair
            validate_repair(current,edited)
        # Keep the editor's original project/timeline identity and schema markers.
        for key in ('id', 'name', 'platform', 'last_modified_platform', 'version', 'create_time'):
            if key in current: edited[key] = copy.deepcopy(current[key])
        paths = {name: T.target_path(str(target), name) for name in T.FILES}
        before = {name: p.read_bytes() if p is not None and p.is_file() else None for name, p in paths.items()}
        T.mirror_updates(before, json.dumps(edited).encode())
        backup = T.checkpoint(str(target), 'before_cli_replace')
        old = T.read_checkpoint(str(target), backup.name)
        for name, p in paths.items():
            live = p.read_bytes() if p is not None and p.is_file() else None
            if live != before[name] or old.get(name) != before[name]:
                raise ValueError('โปรเจกต์เปลี่ยนระหว่างสำรอง ยังไม่ได้แทนผล')
        # Imported assets must survive cleanup of the output folder.
        assets = target/'cli_lab_assets'/uuid.uuid4().hex
        broll_materials=[]
        if ticket.get('contract') == 'broll_only':
            from .broll_assets import additions
            broll_materials=additions(current,edited)
        if ticket.get('contract')=='broll_repair':
            from .broll_assets import repair_materials
            broll_materials=repair_materials(edited)
        # Register every new/replaced local asset, including nested timelines.
        from .cli_lab_story import resolve_media_paths
        original_media=set()
        for node in drafts(current):
            for kind in ('videos','audios'):
                for material in node.get('materials',{}).get(kind,[]):
                    original_media.add((kind,material.get('id'),material.get('path')))
                    # A saved placeholder and its absolute path identify the same
                    # original asset. Do not copy a long source clip just to relink it.
                    try:
                        resolved=resolve_media_paths({'materials':{kind:[material]}},target)
                        value=resolved['materials'][kind][0].get('path')
                        if value:original_media.add((kind,material.get('id'),str(Path(value).resolve())))
                    except ValueError:
                        # A removed/replaced missing original need not block import.
                        pass
        for node in drafts(edited):
            for kind in ('videos','audios'):
                for material in node.get('materials',{}).get(kind,[]):
                    path=Path(material.get('path','')).resolve()
                    if path.is_file() and ((kind,material.get('id'),str(path)) not in original_media or path.is_relative_to(result)):
                        if not any(material is m for m in broll_materials):broll_materials.append(material)
        try:
            progress('กำลังคัดลอกและตรวจไฟล์สื่อเข้าโปรเจกต์')
            for kind in ('videos','audios'):
                for material in (m for node in drafts(edited) for m in node.get('materials',{}).get(kind,[])):
                    path = Path(material.get('path', '')).resolve()
                    if path.is_file() and (path.is_relative_to(result) or any(material is m for m in broll_materials)):
                        assets.mkdir(parents=True, exist_ok=True)
                        dest = assets/(uuid.uuid4().hex[:8]+'_'+path.name)
                        shutil.copyfile(path,dest)
                        if broll_materials:
                            with path.open('rb') as incoming,dest.open('rb') as copied:
                                if hashlib.file_digest(incoming,'sha256').digest()!=hashlib.file_digest(copied,'sha256').digest():raise ValueError('คัดลอกสื่อ B-roll ไม่ครบ ยังไม่แก้โปรเจกต์')
                            expected_stamp=ticket['media'].get(str(path))
                            if expected_stamp and (path.stat().st_size,path.stat().st_mtime_ns)!=tuple(expected_stamp):raise ValueError('สื่อ B-roll เปลี่ยนระหว่างคัดลอก')
                        material['path'] = str(dest)
            # Fresh catalog keys avoid retargeting or overwriting existing entries.
            for material in broll_materials:material['local_material_id']=str(uuid.uuid4()).upper()
            metadata_updates={}
            for name in ('draft_meta_info.json','__project_draft_meta_info.json'):
                if paths[name] is None:continue
                if before[name] is None and not broll_materials:continue
                meta=json.loads(before[name]) if before[name] is not None else dict(draft_id=current.get('id'),draft_name=current.get('name',''))
                meta.update(tm_duration=edited['duration'],tm_draft_modified=int(time.time()*1e6))
                if broll_materials:
                    from .broll_assets import register
                    meta=register(meta,broll_materials,audio_ids={id(m) for node in drafts(edited) for m in node.get('materials',{}).get('audios',[])})
                metadata_updates[name]=json.dumps(meta,ensure_ascii=False).encode('utf-8')
            if ticket.get('contract') == 'broll_only':validate_additions(current,edited)
            if ticket.get('contract')=='broll_repair':validate_repair(current,edited)
            data = json.dumps(edited,ensure_ascii=False).encode('utf-8')
            updates = T.mirror_updates(before, data)
            updates.update({'draft_info_original.json':None,'.spinworld_state.json':None})
            if before['draft_info_backup.json'] is None: updates['draft_info_backup.json']=raw
            updates.update(metadata_updates)
            T.ensure_closed()
            if any((p.read_bytes() if p is not None and p.is_file() else None) != before[name] for name,p in paths.items()):
                raise ValueError('โปรเจกต์เปลี่ยนก่อนแทนผล ยังไม่ได้เขียน')
            # Persist the exact intended fingerprint before changing the project.
            # It makes an interrupted or receipt-failed commit distinguishable from
            # an unstarted one without replaying a write.
            ticket['commit_hash'] = digest(data)
            ticket['commit_updates'] = {name:(digest(value) if value is not None else None) for name,value in updates.items() if T.target_path(str(target),name) is not None}
            ticket['backup_name'] = backup.name
            job_store.save('installs',token,ticket)
            progress('ตรวจไฟล์เสร็จแล้ว กำลังบันทึกโปรเจกต์')
            try: T.replace_files(str(target),updates)
            except BaseException:
                T.replace_files(str(target),{name:before[name] for name in updates}); raise
        except BaseException:
            shutil.rmtree(assets,ignore_errors=True); raise
    from .cli_results import imported
    warning = ''
    try:
        imported(owner, target, result)
        # Keep the compact receipt as evidence if the response or job receipt
        # is lost after the transaction. Source hashes still prevent replay.
    except (OSError, ValueError) as exc:
        warning = 'บันทึกโปรเจกต์แล้ว แต่ยังปรับสถานะรายการผลไม่ได้ โปรดตรวจพื้นที่จัดเก็บและโปรเจกต์ก่อนทำต่อ'
    return {'ok':True,'backup_name':backup.name,'duration':edited['duration']/1e6,
            'warning':warning, 'message':'ใช้ผลกับโปรเจกต์เดิมแล้ว เปิดโปรเจกต์เดิมใน CapCut ได้เลย ย้อนกลับได้จากประวัติ / กู้คืน'}
