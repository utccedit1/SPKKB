"""Add-only Artlist footage: old timeline structures must remain exactly equal."""
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
from . import broll, stock_accounts as A, stock_project as P, event_clip as E
from . import cli_lab as L, cli_lab_story as S, core_engine as CE

ROLE = 'broll_only'
NAME = 'ช่วยด้วยจ้า · B-roll เท่านั้น'


def validate_additions(original, edited):
    """Reject changes to any existing edit, material, timing or project setting."""
    old_tracks = original.get('tracks', [])
    new_tracks = edited.get('tracks', [])[len(old_tracks):]
    if edited.get('tracks', [])[:len(old_tracks)] != old_tracks or not new_tracks:
        raise ValueError('โหมด B-roll เท่านั้นห้ามแก้แทร็กเดิม และต้องมีภาพเพิ่มจริง')
    stripped = copy.deepcopy(edited)
    stripped['tracks'] = copy.deepcopy(old_tracks)
    old_materials = original.get('materials', {})
    if not set(old_materials).issubset(edited.get('materials',{})):raise ValueError('วัสดุเดิมหาย')
    new_ids = set()
    for kind, values in edited.get('materials', {}).items():
        before = old_materials.get(kind, [])
        if not isinstance(values, list):
            if values != before:raise ValueError('วัสดุเดิมเปลี่ยน')
            continue
        if values[:len(before)] != before:raise ValueError('วัสดุเดิมเปลี่ยน')
        additions = values[len(before):]
        if additions and kind not in ('videos','speeds','canvases','sound_channel_mappings','material_colors','placeholder_infos','vocal_separations'):
            raise ValueError('โหมดนี้เพิ่มได้เฉพาะวัสดุสำหรับภาพ B-roll: '+kind)
        for m in additions:
            if not isinstance(m,dict) or not m.get('id') or m['id'] in new_ids:raise ValueError('รหัสวัสดุเพิ่มไม่ถูกต้อง')
            new_ids.add(m['id'])
    stripped['materials'] = copy.deepcopy(old_materials)
    if stripped != original:raise ValueError('โหมด B-roll เท่านั้นตรวจพบการเปลี่ยนการตัดต่อเดิม จึงหยุดนำเข้า')
    existing_ids = {m.get('id') for values in old_materials.values() if isinstance(values,list) for m in values if isinstance(m,dict)}
    if new_ids & existing_ids:raise ValueError('รหัสวัสดุใหม่ชนกับวัสดุเดิม')
    videos = {m['id'] for m in edited.get('materials',{}).get('videos',[]) if m.get('id') in new_ids}
    ids = {s.get('id') for t in old_tracks for s in t.get('segments',[])}
    track_ids={t.get('id') for t in old_tracks}
    layer=layer_index(original)
    for track in new_tracks:
        if not track.get('id') or track['id'] in track_ids:raise ValueError('รหัสแทร็กใหม่ชนกับงานเดิม')
        track_ids.add(track['id'])
        if track.get('type')!='video' or track.get('ks_role')!=ROLE or not track.get('segments'):
            raise ValueError('เพิ่มได้เฉพาะแทร็ก B-roll ที่แยกจากงานเดิม')
        for seg in track['segments']:
            tr=seg.get('target_timerange',{});a=tr.get('start');n=tr.get('duration')
            if seg.get('material_id') not in videos or seg.get('volume')!=0 or not seg.get('id') or seg.get('id') in ids:
                raise ValueError('ภาพเพิ่มต้องใช้วัสดุใหม่และปิดเสียง')
            ids.add(seg.get('id'))
            if seg.get('render_index')!=layer or not set(seg.get('extra_material_refs',[])).issubset(new_ids):
                raise ValueError('B-roll ต้องอยู่เหนือภาพหลักและใต้ซับ โดยไม่ใช้เอฟเฟกต์ของคลิปเดิม')
            if any(isinstance(v,bool) or not isinstance(v,int) for v in (a,n)) or a<0 or n<=0 or a+n>original['duration']:
                raise ValueError('B-roll ต้องอยู่ภายในความยาวไทม์ไลน์เดิม')


def layer_index(draft):
    main=next((t for t in draft.get('tracks',[]) if t.get('type')=='video' and not t.get('attribute',0)&1),None)
    if main is None:raise ValueError('ไม่พบแทร็กวิดีโอหลักสำหรับวาง B-roll')
    lower=max((s.get('render_index',0) for s in main.get('segments',[])),default=0)
    captions=[s.get('render_index',0) for t in draft.get('tracks',[]) if t.get('type')=='text' for s in t.get('segments',[])]
    if captions and min(captions)<=lower+1:
        raise ValueError('ลำดับภาพกับซับของโปรเจกต์นี้ยังวาง B-roll โดยคงซับเดิมไม่ได้ จึงไม่แก้ไทม์ไลน์')
    return lower+1


def build(owner, project, cfg, progress):
    if cfg.get('media_kind','footage')!='footage':raise ValueError('โหมดอัตโนมัตินี้ใช้ฟุตเทจ Artlist เท่านั้น มีมยังใช้ค้นคำแบบเดิม')
    if cfg.get('provider','artlist')!='artlist':raise ValueError('โหมดนี้รองรับ Artlist เท่านั้น')
    maximum=cfg.get('max_shots',8)
    if isinstance(maximum,bool) or not isinstance(maximum,int) or not 1<=maximum<=30:raise ValueError('เลือกจำนวนภาพได้ 1–30 ช็อต')
    path=Path(project).resolve();raw=(path/'draft_info.json').read_bytes();original=json.loads(raw)
    duration=original.get('duration',0)/1e6
    if not math.isfinite(duration) or duration<=0:raise ValueError('ความยาวไทม์ไลน์ไม่ถูกต้อง')
    layer=layer_index(original)
    A.ensure_ready(owner,'artlist',progress)
    destination=P.settings(owner,path)['destination']
    report=[]
    with tempfile.TemporaryDirectory(prefix='ks-broll-only-') as folder:
        work=Path(folder).resolve();(work/'draft_info.json').write_bytes(raw)
        previous=getattr(E._CONTEXT,'progress',None)
        E._CONTEXT.progress=lambda **v:progress(v.get('message','กำลังเตรียม B-roll'))
        try:ideas=broll.api_broll(str(work),dict(cfg,media_kind='footage',stock_auto=True))
        finally:
            if previous is None:E._CONTEXT.__dict__.pop('progress',None)
            else:E._CONTEXT.progress=previous
        if not ideas.get('ok'):raise ValueError(ideas.get('error','ยังไม่มีคำค้น B-roll'))
        if (path/'draft_info.json').read_bytes()!=raw:raise ValueError('ไทม์ไลน์เปลี่ยนระหว่างหาไอเดีย กรุณาเริ่มใหม่')
        edited=copy.deepcopy(original);last_end=-3
        for item in ideas.get('items',[])[:maximum*2]:
            if sum(r.get('state')=='inserted' for r in report)>=maximum:break
            progress(f'เตรียม B-roll {sum(r.get("state")=="inserted" for r in report)}/{maximum} ภาพ · '+str(item.get('query','')))
            a,b=item.get('start'),item.get('end')
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (a,b)) or not 0<=a<b<=duration:continue
            from .media_schedule import occupied
            start=max(a,last_end+3);end=min(b,start+6,duration)
            if end-start<.5 or any(start<right and end>left for left,right in occupied(edited)):
                report.append(dict(state='skipped',query=item['query'],reason='มีภาพประกอบเดิมหรือช่วงภาพชนกัน'));continue
            searches=[item.get('query')]+list(item.get('keywords') or [])
            searches=list(dict.fromkeys(q for q in searches if broll.english_query(q)))[:3]
            record=None
            for query in searches:
                request=dict(kind='broll',query=query,required_terms=[],exclude_urls=[r['url'] for r in report if r.get('url')],exclude_hashes=[r['sha256'] for r in report if r.get('sha256')])
                try:record=A.wait_download(owner,'artlist',request,progress)
                except A.StockDownloadError as exc:
                    if exc.code not in ('no_match','page_not_ready','search_failed','timeout','download_failed','download_controls','file_access_timeout'):raise
                    report.append(dict(state='failed_search',query=query,reason=str(exc)));record=None
                if record:break
            if record is None:
                report.append(dict(state='skipped',query=item['query'],reason='ไม่พบไฟล์ที่ดาวน์โหลดและตรวจได้'));continue
            if any(record.get('sha256')==r.get('sha256') or record.get('url')==r.get('url') for r in report if r.get('state')=='inserted'):
                report.append(dict(state='skipped',query=item['query'],reason='ไฟล์ซ้ำ'));continue
            length=min(end-start,float(record['duration']))
            if not math.isfinite(length) or length<.5:continue
            media=P.store(record['path'],destination,'B-roll',record.get('title','B-roll'))
            from .stock_polish import frame_video
            prepared,framing=frame_video(media,work,original.get('canvas_config') or {},length)
            media=P.store(prepared,destination,'Prepared',record.get('title','B-roll'))
            # CLI sees only an empty import draft, never existing user tracks/materials.
            scratch=work/'import';scratch.mkdir(exist_ok=True)
            empty=copy.deepcopy(original);empty['tracks']=[];empty['materials']={k:[] for k,v in original.get('materials',{}).items() if isinstance(v,list)}
            (scratch/'draft_info.json').write_text(json.dumps(empty,ensure_ascii=False))
            L.run_cli('add-video',scratch,media,start,length,'--track-name',NAME,'--ffprobe-cmd',CE.ac_ffprobe_bin() or 'ffprobe')
            added=json.loads((scratch/'draft_info.json').read_bytes())
            # Only new materials may be rewritten to stable storage paths.
            for kind, values in added.get('materials',{}).items():
                if kind not in ('videos','audios'):continue
                for material in values:
                    value=material.get('path')
                    if value and Path(value).is_file() and Path(value).resolve().is_relative_to(work):
                        material['path']=P.store(value,destination,'Prepared',record.get('title','B-roll'))
            from .stock_media import fill_frame
            for track in added['tracks']:
                if track.get('type')!='video':raise ValueError('เครื่องมือนำเข้าสร้างแทร็กที่ไม่ใช่ภาพ')
                track.update(ks_role=ROLE,name=NAME)
                for seg in track.get('segments',[]):
                    seg.update(volume=0,render_index=layer)
                    fill_frame(added,seg)
                edited['tracks'].append(track)
            for kind,values in added.get('materials',{}).items():
                if values:edited['materials'].setdefault(kind,[]).extend(values)
            validate_additions(original,edited)
            report.append(dict(state='inserted',query=item['query'],start=start,duration=length,url=record.get('url'),sha256=record.get('sha256'),framing=framing))
            last_end=start+length
        count=sum(r.get('state')=='inserted' for r in report)
        if not count:raise ValueError('ยังไม่มี B-roll ที่ใส่ได้ จึงไม่สร้างผลหรือแก้โปรเจกต์ ลองคำค้น/บัญชีหรือช่วงอื่น')
        progress('ตรวจว่าการตัดต่อเดิมทั้งหมดคงเดิมก่อนบันทึกผล')
        if (path/'draft_info.json').read_bytes()!=raw:raise ValueError('โปรเจกต์เปลี่ยนระหว่างหา B-roll ยังไม่แก้โปรเจกต์')
        validate_additions(original,edited)
        # Keep imported absolute media references alive beyond the temporary scratch.
        output=S.publish(work,edited,Path(CE.CONFIG_DIR)/'cli_lab_outputs')
        (output/'broll_only_report.json').write_text(json.dumps(dict(inserted=count,items=report),ensure_ascii=False,indent=2))
        final=json.loads((output/'draft_info.json').read_bytes());validate_additions(original,final)
        from .cli_results import remember
        token=remember(owner,path,output,hashlib.sha256(raw).hexdigest(),'broll_only')
    return dict(ok=True,result_id=token,destination=str(output),inserted=count,items=report,message=f'เตรียม B-roll {count} ช็อตแล้ว การตัดต่อเดิมคงเดิม ตรวจรายการแล้วกดใส่ B-roll')
