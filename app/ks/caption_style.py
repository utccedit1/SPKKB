"""Bulk style edits without invoking CapCut's rich-caption bulk editor or AI."""
import copy,json,hashlib,math
from pathlib import Path
from collections import Counter
from . import event_clip as E,event_timeline as T


def run(proj,cfg):
    T.ensure_closed(home_confirmed=cfg.get('capcut_home_confirmed') is True);path=Path(proj)/'draft_info.json';raw=path.read_bytes();draft=json.loads(raw)
    if cfg.get('state_hash')!=hashlib.sha1(raw).hexdigest():raise ValueError('กรุณาโหลดซับไทม์ไลน์ล่าสุดก่อนปรับฟอนต์')
    ns=float(cfg.get('normal_size',12));hs=float(cfg.get('highlight_size',16))
    if not all(math.isfinite(s) and 1<=s<=100 for s in (ns,hs)):raise ValueError('ขนาดฟอนต์ต้องอยู่ระหว่าง 1–100')
    font=cfg.get('font') or ''
    if font and not Path(font).is_file():raise ValueError('ไม่พบไฟล์ฟอนต์ที่เลือก')
    if font:
        from font_metadata import native_path
        font=native_path(font)
    rows=E.CE.text_segments(draft);only=cfg.get('only')
    if only is not None:
        if not isinstance(only,list) or any(type(i)!=int for i in only):raise ValueError('รายการซับไม่ถูกต้อง')
        if set(only)-{r[0] for r in rows}:raise ValueError('ซับที่เลือกไม่อยู่ในไทม์ไลน์')
    generated={s['id'] for t in draft['tracks'] if t.get('name') in ('Super Text','ช่วยด้วยจ้า Box') for s in t.get('segments',[])}
    rows=[r for r in rows if r[2] and r[1]['id'] not in generated and (only is None or r[0] in only)]
    if not rows:raise ValueError('ไม่มีซับหลักที่เลือก')
    def color(style):return tuple(style.get('fill',{}).get('content',{}).get('solid',{}).get('color',[]))
    weights=Counter()
    for i,s,m,text in rows:
        for st in json.loads(m['content']).get('styles',[]):
            r=st.get('range',[0,1]);weights[color(st)]+=max(1,r[1]-r[0])
    normal=weights.most_common(1)[0][0] if weights else ()
    patches={};mapping={}
    for i,s,m,text in rows:
        material=copy.deepcopy(m);content=json.loads(material['content'])
        for st in content.get('styles',[]):
            st['size']=ns if color(st)==normal else hs
            if font:st['font']={'id':'','path':font}
        material['content']=json.dumps(content,ensure_ascii=False)
        if 'base_content' in material:material['base_content']=material['content']
        material['font_size']=ns
        if font:E.CE.apply_font(material,font)
        material['id']=E.CE.nid();mapping[s['id']]=material['id'];patches[material['id']]=material
    T.ensure_closed(home_confirmed=cfg.get('capcut_home_confirmed') is True)
    if path.read_bytes()!=raw:raise ValueError('โปรเจกต์เปลี่ยนระหว่างทำงาน ยังไม่ได้แก้ไฟล์')
    E.progress(message='กำลังสำรองและปรับฟอนต์ซับ',commit_started=True)
    backup=T.checkpoint(proj,'before_caption_style');old=T.read_checkpoint(proj,backup.name)
    if old['draft_info.json']!=raw:raise ValueError('โปรเจกต์เปลี่ยนระหว่างสำรอง')
    updated={};rollback={}
    for name in ('draft_info.json','__project_draft_info.json'):
        payload=old.get(name)
        if payload is None:continue
        live=json.loads(payload)
        if live.get('id')!=draft.get('id'):raise ValueError('ไทม์ไลน์หลักไม่ตรงกัน')
        found=set()
        for track in live['tracks']:
            for seg in track.get('segments',[]):
                if seg['id'] in mapping:seg['material_id']=mapping[seg['id']];found.add(seg['id'])
        if found!=set(mapping):raise ValueError('สำเนาไทม์ไลน์มีซับไม่ตรงกัน')
        live['materials']['texts'].extend(patches.values());E.CE._gc_unused_text(live)
        updated[name]=json.dumps(live,ensure_ascii=False).encode();rollback[name]=payload
    state=json.loads(old.get('.spinworld_state.json') or b'{}');state['output_hash']=hashlib.sha1(updated['draft_info.json']).hexdigest()
    updated['.spinworld_state.json']=json.dumps(state).encode();rollback['.spinworld_state.json']=old.get('.spinworld_state.json')
    T.ensure_closed(home_confirmed=cfg.get('capcut_home_confirmed') is True)
    if path.read_bytes()!=raw:raise ValueError('โปรเจกต์เปลี่ยนก่อนบันทึก')
    try:T.replace_files(proj,updated)
    except Exception:T.replace_files(proj,rollback);raise
    return {'ok':True,'msg':f'ปรับฟอนต์/ขนาด {len(rows)} ชิ้น คง Caption สีคาราโอเกะและเวลาเดิม','backup_name':backup.name}
