"""Register only added B-roll in CapCut's local media catalog."""
import copy
from pathlib import Path
import uuid


def additions(original, edited):
    ids={m.get('id') for m in original.get('materials',{}).get('videos',[])}
    return [m for m in edited.get('materials',{}).get('videos',[]) if m.get('id') not in ids]


def register(metadata, materials):
    result=copy.deepcopy(metadata)
    groups=result.setdefault('draft_materials',[])
    if not isinstance(groups,list):raise ValueError('ทะเบียนสื่อ CapCut อ่านไม่ได้ ยังไม่นำเข้า')
    group=next((g for g in groups if g.get('type')==0),None)
    if group is None:group={'type':0,'value':[]};groups.append(group)
    if not isinstance(group.get('value'),list):raise ValueError('ทะเบียนสื่อ CapCut อ่านไม่ได้')
    for material in materials:
        path=Path(material['path'])
        if not path.is_absolute() or not path.is_file():raise ValueError('ไม่พบสื่อ B-roll ก่อนลงทะเบียน: '+str(path))
        key=material.get('local_material_id') or str(uuid.uuid4()).upper()
        material['local_material_id']=key
        found=[e for g in groups for e in g.get('value',[]) if e.get('id')==key]
        if found:
            if any(e.get('file_Path')!=str(path) for e in found):raise ValueError('รหัสสื่อ B-roll ชนกับทะเบียนเดิม')
            continue
        group['value'].append(dict(ai_group_type='',create_time=-1,duration=material.get('duration',0),enter_from=0,
            extra_info=path.name,file_Path=str(path),height=material.get('height',0),width=material.get('width',0),
            id=key,import_time=-1,import_time_ms=-1,item_source=1,material_color_tag='',md5='',metetype='video',
            roughcut_time_range=dict(duration=-1,start=-1),sub_time_range=dict(duration=-1,start=-1),type=0))
    return result


def repair_materials(draft):
    from .broll_auto import NAME
    def owned(track):
        return track.get('type')=='video' and bool(track.get('segments')) and (track.get('ks_role')=='broll_only' or track.get('name')==NAME) and all(s.get('volume')==0 for s in track['segments'])
    ids={s.get('material_id') for t in draft.get('tracks',[]) if owned(t) for s in t.get('segments',[])}
    other={s.get('material_id') for t in draft.get('tracks',[]) if not owned(t) for s in t.get('segments',[])}
    if not ids or ids & other:raise ValueError('ไม่พบ B-roll ที่แยกจากงานเดิมอย่างปลอดภัย')
    return [m for m in draft.get('materials',{}).get('videos',[]) if m.get('id') in ids]


def validate_repair(original,edited):
    restored=copy.deepcopy(edited);before={m['id']:m for m in repair_materials(original)}
    for m in repair_materials(restored):
        for key in ('path','local_material_id'):
            if key in before[m['id']]:m[key]=before[m['id']][key]
            else:m.pop(key,None)
    if restored!=original:raise ValueError('ซ่อมได้เฉพาะตำแหน่งและทะเบียน B-roll ไม่แก้การตัดต่ออื่น')


def prepare_repair(owner,project):
    import hashlib,json,tempfile
    from . import cli_lab_story as S,cli_results as R,core_engine as CE
    project=Path(project).resolve();raw=(project/'draft_info.json').read_bytes();draft=json.loads(raw)
    # Resolve only B-roll; never change or relink the user's original media.
    selected=repair_materials(draft)
    resolved=S.resolve_media_paths({'materials':{'videos':copy.deepcopy(selected)}},project)['materials']['videos']
    for material,real in zip(selected,resolved):
        if not Path(real['path']).is_file():raise ValueError('ไฟล์ B-roll หายจริง ยังซ่อมอัตโนมัติไม่ได้: '+real['path'])
        material['path']=real['path']
    validate_repair(json.loads(raw),draft)
    with tempfile.TemporaryDirectory(prefix='ks-broll-repair-') as folder:
        output=S.publish(Path(folder),draft,Path(CE.CONFIG_DIR)/'cli_lab_outputs')
    (output/'broll_repair_report.json').write_text(json.dumps({'count':len(selected)}))
    token=R.remember(owner,project,output,hashlib.sha256(raw).hexdigest(),'broll_repair')
    return R.review(owner,project,token)
