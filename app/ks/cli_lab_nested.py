"""Read selected audio from native compound/multicam drafts without flattening video."""
import copy
from pathlib import Path
import uuid


def drafts(root):
    yield root
    for material in root.get('materials',{}).get('drafts',[]):
        child=material.get('draft')
        if isinstance(child,dict):yield from drafts(child)


def audio_view(root):
    result=copy.deepcopy(root);leafs=[];materials={'videos':[],'audios':[]}
    for node in drafts(root):
        for kind,values in node.get('materials',{}).items():
            if kind not in ('videos','audios','drafts') and isinstance(values,list):materials.setdefault(kind,[]).extend(copy.deepcopy(values))
    def walk(draft,begin,end,output,rate,volume,selected=None,depth=0):
        if depth>8:raise ValueError('โปรเจกต์ย่อยซ้อนเกิน 8 ชั้น ยังอ่านเสียงไม่ได้')
        lookup={m['id']:m for k in ('videos','audios') for m in draft.get('materials',{}).get(k,[])}
        nested={m['id']:m.get('draft') for m in draft.get('materials',{}).get('drafts',[])}
        speeds={m['id']:m for m in draft.get('materials',{}).get('speeds',[])}
        for track in draft.get('tracks',[]):
            if track.get('type') not in ('video','audio') or track.get('attribute',0)&1:continue
            if selected is not None and track.get('id') not in selected:continue
            name=str(track.get('name',''))
            if track.get('ks_role') in ('music','sfx','overlay') or name.startswith('ช่วยด้วยจ้า ·'):continue
            import re
            if re.search(r'music|bgm|sfx|เพลง|ดนตรี|เอฟเฟกต์เสียง',name,re.I):continue
            for s in track.get('segments',[]):
                tr=s.get('target_timerange') or {};left=max(begin,tr.get('start',0));right=min(end,tr.get('start',0)+tr.get('duration',0))
                m=lookup.get(s.get('material_id'),{});gain=volume*float(s.get('volume',1))
                if right<=left or gain<=0 or m.get('has_audio') is False:continue
                speed=s.get('speed',1)
                if not isinstance(speed,(int,float)) or isinstance(speed,bool) or not .125<=speed<=8:raise ValueError('ความเร็วเสียงในโปรเจกต์ย่อยไม่รองรับ')
                if s.get('reverse') or s.get('is_reverse') or any((speeds.get(ref) or {}).get('curve_speed') for ref in s.get('extra_material_refs',[])):raise ValueError('เสียง multicam เล่นย้อนกลับหรือมีกราฟความเร็ว ยังจับเวลาไม่ได้')
                src=(s.get('source_timerange') or {}).get('start',0)+(left-tr['start'])*speed
                size=(right-left)*speed;at=output+(left-begin)/rate
                child=next((nested[ref] for ref in s.get('extra_material_refs',[]) if isinstance(nested.get(ref),dict)),None)
                if child is not None:
                    info=m.get('multi_camera_info') or {}
                    chosen=info.get('audio_open_track_id_list') if info else None
                    if info and not isinstance(chosen,list):raise ValueError('ไม่พบการเลือกกล้องเสียงของ multicam กรุณาเลือกเสียงใน CapCut ก่อน')
                    if any(g.get('property_type')=='KFTypeVolume' and g.get('keyframe_list') for g in s.get('common_keyframes',[])):raise ValueError('คลิป multicam ชั้นนอกมีคีย์เฟรมความดังที่ยังอ่านไม่ได้ กรุณาใช้เสียงแยกในสำเนา')
                    if chosen and not set(chosen).issubset({t.get('id') for t in child.get('tracks',[])}):raise ValueError('กล้องเสียง multicam อ้างแทร็กที่ไม่พบ')
                    walk(child,src,src+size,at,rate*speed,gain,chosen,depth+1);continue
                refs=set(s.get('extra_material_refs',[]))
                effects=draft.get('materials',{}).get('audio_effects',[])+[v for v in draft.get('materials',{}).get('vocal_separations',[]) if v.get('choice',0)]
                if any(v.get('id') in refs for v in effects):raise ValueError('เสียงในโปรเจกต์ย่อยมีเอฟเฟกต์ที่ยังจำลองไม่ได้ กรุณาใช้เสียงแยกในสำเนา')
                media=m.get('path')
                if not media or not Path(media).is_file():raise ValueError('ไม่พบไฟล์เสียงต้นฉบับ: '+str(m.get('material_name') or m.get('name') or media or s.get('material_id')))
                material=copy.deepcopy(m);material['id']=uuid.uuid4().hex;materials['audios'].append(material)
                seg=copy.deepcopy(s);seg.update(id=uuid.uuid4().hex,material_id=material['id'],speed=rate*speed,volume=gain,
                    source_timerange=dict(start=round(src),duration=round(size)),target_timerange=dict(start=round(at),duration=round((right-left)/rate)))
                for group in seg.get('common_keyframes',[]):
                    if group.get('property_type')=='KFTypeVolume':
                        for key in group.get('keyframe_list',[]):key['values']=[v*volume for v in key.get('values',[])]
                leafs.append(seg)
    walk(root,0,root['duration'],0,1,1)
    result['materials']=materials;result['tracks']=[dict(type='audio',name='speech',segments=leafs)]
    return result
