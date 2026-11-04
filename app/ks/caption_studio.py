"""Owned local caption previews and non-destructive native style copies."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import uuid
from . import caption_presets as P

_assets={}
_active=0
_preview_temp=tempfile.TemporaryDirectory(prefix="chuaydai-caption-preview-")
_guard=threading.RLock()
_render_lock=threading.Semaphore(2)


def fingerprint(raw):return hashlib.sha256(raw).hexdigest()
def available_fonts():
    from . import core_engine as CE
    return CE.list_fonts()
def output_root():
    from .ce_config import CONFIG_DIR
    return Path(CONFIG_DIR)/'caption_studio'
def _scope(owner,workspace,project):
    if not owner or not workspace:raise ValueError('ไม่พบผู้ใช้หรือหน้าต่างงาน')
    return str(owner),str(workspace),str(Path(project).resolve())
def _stamp(path):
    st=Path(path).stat();return st.st_size,st.st_mtime_ns

def register_asset(owner,workspace,project,path,source_hash,source=None):
    token=uuid.uuid4().hex;path=Path(path)
    with _guard:
        if len(_assets)>=200:
            # Revoke oldest tokens; do not delete files while an HTTP reader holds them.
            old=_assets.pop(next(iter(_assets)))
            if old['path'].is_relative_to(Path(_preview_temp.name)):
                shutil.rmtree(old['path'].parent,ignore_errors=True)
        _assets[token]=dict(scope=_scope(owner,workspace,project),path=path,stamp=_stamp(path),source_hash=source_hash,source=Path(source) if source else None,source_stamp=_stamp(source) if source else None)
    return token

def asset(owner,workspace,project,token):
    with _guard:row=_assets.get(token)
    if not row or row['scope']!=_scope(owner,workspace,project):raise ValueError('ไม่พบพรีวิวของหน้าต่างนี้')
    if fingerprint((Path(project)/'draft_info.json').read_bytes())!=row['source_hash'] or _stamp(row['path'])!=row['stamp']:raise ValueError('ข้อมูลเปลี่ยนแล้ว กรุณาโหลดพรีวิวใหม่')
    if row.get('media_hash') and media_fingerprint(json.loads((Path(project)/'draft_info.json').read_bytes()),project)!=row['media_hash']:raise ValueError('สื่อเปลี่ยนแล้ว กรุณาสร้างพรีวิวใหม่')
    if row['source'] and _stamp(row['source'])!=row['source_stamp']:raise ValueError('ไฟล์วิดีโอเปลี่ยนแล้ว')
    return row['path']


def source_at(draft,at,_depth=0):
    """Pick the base visible source, never pretend to composite native effects."""
    if _depth>8:raise ValueError('multicam ซ้อนลึกเกินไป')
    lookup={m['id']:m for m in draft.get('materials',{}).get('videos',[])}
    nested={m.get('id'):m for m in draft.get('materials',{}).get('drafts',[])}
    speeds={m.get('id'):m for m in draft.get('materials',{}).get('speeds',[])}
    for track in draft.get('tracks',[]):
        if track.get('type')!='video' or track.get('attribute',0)&1:continue
        for seg in track.get('segments',[]):
            tr=seg.get('target_timerange') or {};start=tr.get('start',0)/1e6;end=(tr.get('start',0)+tr.get('duration',0))/1e6
            if not start<=at<end:continue
            refs=seg.get('extra_material_refs',[])
            if any((speeds.get(r) or {}).get('curve_speed') for r in refs) or seg.get('reverse') or seg.get('is_reverse'):raise ValueError('พรีวิว compound / multicam / กราฟความเร็วนี้ยังไม่ได้ โปรดตรวจใน CapCut')
            speed=seg.get('speed',1)
            if isinstance(speed,bool) or not isinstance(speed,(int,float)) or not math.isfinite(speed) or not .125<=speed<=8:raise ValueError('อ่านความเร็วคลิปไม่ได้')
            material=lookup.get(seg.get('material_id'),{})
            children=[nested[r] for r in refs if r in nested]
            if children:
                camera=material.get('multi_camera_info') or {}
                selected=camera.get('cur_camera_track_id')
                if len(children)!=1 or not selected:raise ValueError('พรีวิว compound นี้ยังไม่ได้ โปรดตรวจใน CapCut')
                child=children[0].get('draft')
                if not isinstance(child,dict):raise ValueError('อ่าน multicam ไม่ได้')
                tracks=[t for t in child.get('tracks',[]) if t.get('id')==selected and t.get('type')=='video']
                if len(tracks)!=1:raise ValueError('ไม่พบกล้องที่เลือกใน multicam')
                child=dict(child,tracks=tracks)
                local=(seg.get('source_timerange') or {}).get('start',0)/1e6+(at-start)*speed
                result=source_at(child,local,_depth+1)
                result['remaining']=min(end-at,result['remaining']/speed)
                result['speed']*=speed
                result['volume']*=max(0,float(seg.get('volume',1)))
                result['audio']=result['audio'] and camera.get('audio_open_track_id_list')==[selected] and not seg.get('common_keyframes')
                return result
            path=material.get('path','')
            if not path or not Path(path).is_file():raise ValueError('ไม่พบวิดีโอต้นฉบับของช่วงนี้')
            return dict(path=path,photo=material.get('type')=='photo',speed=speed,volume=max(0,float(seg.get('volume',1))),audio=material.get('has_audio') is not False and not seg.get('common_keyframes'),offset=(seg.get('source_timerange') or {}).get('start',0)/1e6+(at-start)*speed,remaining=end-at)
    raise ValueError('ช่วงนี้ไม่มีภาพต้นฉบับที่พรีวิวได้ ยังเลือกสไตล์จากการ์ดได้')


def _read(project,expected=None):
    raw=(Path(project)/'draft_info.json').read_bytes()
    if expected is not None and fingerprint(raw)!=expected:raise ValueError('ไทม์ไลน์เปลี่ยนแล้ว กรุณาโหลดซับใหม่')
    return raw,json.loads(raw)


def media_fingerprint(draft,project):
    from .cli_lab_story import resolve_media_paths
    from .cli_lab_nested import drafts
    resolved=resolve_media_paths(draft,project);stamps=[]
    for node in drafts(resolved):
        used={seg.get('material_id') for track in node.get('tracks',[]) for seg in track.get('segments',[])}
        for kind in ('videos','audios'):
            for m in node.get('materials',{}).get(kind,[]):
                if m.get('id') in used and m.get('path'):
                    path=Path(m['path']).resolve()
                    if not path.is_file():raise ValueError('ไม่พบสื่อในไทม์ไลน์ กรุณาตรวจใน CapCut')
                    stamps.append((str(path),*_stamp(path)))
    return fingerprint(json.dumps(sorted(stamps)).encode())


def handle(owner,workspace,project,data):
    from . import job_admission as A
    global _active
    with A.lock:
        if A.updating:raise ValueError('กำลังอัปเดตโปรแกรม กรุณารอก่อน')
        _active+=1
    try:return _handle(owner,workspace,project,data)
    finally:
        with A.lock:_active-=1


def _handle(owner,workspace,project,data):
    scope=_scope(owner,workspace,project)
    if not isinstance(data,dict):raise ValueError('คำขอไม่ถูกต้อง')
    action=data.get('action');raw,draft=_read(project,None if action=='metadata' else data.get('source_hash',''))
    rows=P.caption_rows(draft)
    media_hash=media_fingerprint(draft,project)
    if action!='metadata' and data.get('media_hash')!=media_hash:raise ValueError('สื่อเปลี่ยนแล้ว กรุณาโหลดซับและพรีวิวใหม่')
    if action=='metadata':
        from . import core_engine as CE
        config=CE.load_config();fonts=available_fonts()
        from .cli_lab_typography import editorial_font
        font=config.get('font') or editorial_font();font=font if font in {f['path'] for f in fonts} else ''
        return dict(ok=True,source_hash=fingerprint(raw),media_hash=media_hash,canvas=draft.get('canvas_config') or dict(width=1080,height=1920),cues=[dict(id=s['id'],text=text,start=s['target_timerange']['start']/1e6,duration=s['target_timerange']['duration']/1e6) for _,s,m,text in rows],presets=P.catalog(),fonts=fonts,defaults=dict(font=font),note='พรีวิวภาพต้นฉบับและซับใหม่โดยประมาณ ไม่รวมการซ้อนภาพ เอฟเฟกต์ และมิกซ์เสียงเดิมทั้งหมด ต้องตรวจผลใน CapCut')
    if action=='full_proxy':
        from .kinetic_proxy import build
        return build(owner,workspace,project,raw,draft,media_hash)
    if action=='style':
        cfg=P.settings(data.get('settings',{}),available_fonts())
        cue=next(((s,m,text) for _,s,m,text in rows if s['id']==data.get('cue_id')),None)
        if cue is None:raise ValueError('ไม่พบซับที่เลือก')
        s,m,text=cue;canvas=draft.get('canvas_config') or {}
        return dict(ok=True,settings=cfg,text=text,motion=P.motion(cfg,s['target_timerange']['duration']),layout=P.layout(text,cfg,canvas.get('width',1080),canvas.get('height',1920)))
    if action=='prepare':
        cfg=P.settings(data.get('settings',{}),available_fonts())
        ids=data.get('ids')
        if data.get('scope')=='all':ids=[s['id'] for _,s,m,text in rows]
        from .cli_lab_nested import drafts
        if any(P.caption_rows(node) for node in list(drafts(draft))[1:]):raise ValueError('โปรเจกต์มีซับใน compound ให้เลือกไทม์ไลน์ที่มีซับโดยตรงก่อน เพื่อไม่เปลี่ยนไม่ครบ')
        count=P.apply(draft,ids,cfg)
        from .cli_lab_story import resolve_media_paths
        draft=resolve_media_paths(draft,project)
        root=output_root()/fingerprint('\0'.join(scope).encode())
        root.mkdir(parents=True,exist_ok=True);folder=Path(tempfile.mkdtemp(prefix='style-',dir=root))
        try:
            (folder/'draft_info.json').write_text(json.dumps(draft,ensure_ascii=False),encoding='utf-8')
            (folder/'caption_studio_report.json').write_text(json.dumps(dict(count=count,preset=cfg['preset'],native_review_required=True),ensure_ascii=False),encoding='utf-8')
            _read(project,fingerprint(raw))
            if media_fingerprint(draft,project)!=media_hash:raise ValueError('สื่อเปลี่ยนระหว่างสร้างสำเนา')
            from .cli_results import remember
            result_id=remember(owner,project,folder,fingerprint(raw),'caption_style')
        except BaseException:
            shutil.rmtree(folder,ignore_errors=True);raise
        return dict(ok=True,result_id=result_id,destination=str(folder),count=count,message=f'สร้างสำเนาสไตล์ซับ {count} ชิ้นแล้ว ตรวจและนำเข้าผ่านขั้นตอนเดิม')
    if action=='preview':
        chosen=next((s for _,s,m,t in rows if s['id']==data.get('cue_id')),None)
        if chosen is None:raise ValueError('ไม่พบซับที่เลือก')
        from .cli_lab_story import resolve_media_paths
        draft=resolve_media_paths(draft,project)
        start=chosen['target_timerange']['start']/1e6;source=source_at(draft,start)
        duration=min(12.,chosen['target_timerange']['duration']/1e6,source['remaining'])
        if duration<=0:raise ValueError('ซับไม่มีระยะเวลาให้พรีวิว')
        if not _render_lock.acquire(blocking=False):raise ValueError('กำลังสร้างพรีวิวอื่น กรุณารอสักครู่')
        folder=None
        try:
            root=Path(_preview_temp.name)/fingerprint('\0'.join(scope).encode());root.mkdir(parents=True,exist_ok=True)
            folder=Path(tempfile.mkdtemp(prefix='preview-',dir=root));out=folder/'source.mp4'
            before=_stamp(source['path'])
            from . import core_engine as CE
            binary=CE.ac_ffmpeg_bin()
            if not binary:raise ValueError('ไม่พบเครื่องมือสร้างพรีวิว')
            args=[binary,'-nostdin','-v','error','-y']
            args+=['-loop','1'] if source['photo'] else ['-ss',str(source['offset'])]
            args+=['-i',source['path'],'-t',str(duration)]
            audible=source['audio'] and not source['photo'] and source['volume']>0
            if audible:
                remaining=source['speed'];factors=[]
                while remaining>2:factors.append('atempo=2');remaining/=2
                while remaining<.5:factors.append('atempo=0.5');remaining/=.5
                factors.extend(['atempo='+str(remaining),'volume='+str(source['volume'])])
                args+=['-map','0:v:0','-map','0:a:0?','-af',','.join(factors),'-c:a','aac']
            else:args+=['-an']
            args+=['-vf',f"setpts=(PTS-STARTPTS)/{source['speed']},scale=960:960:force_original_aspect_ratio=decrease:force_divisible_by=2",'-r','30','-c:v','libx264','-preset','ultrafast','-crf','24','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
            run=subprocess.run(args,capture_output=True,timeout=60)
            if run.returncode or not out.is_file():raise ValueError('สร้างภาพพรีวิวไม่ได้ กรุณาตรวจสื่อใน CapCut')
            _read(project,fingerprint(raw))
            if before!=_stamp(source['path']):raise ValueError('สื่อเปลี่ยนระหว่างสร้างพรีวิว')
            token=register_asset(owner,workspace,project,out,fingerprint(raw),source['path'])
            return dict(ok=True,token=token,duration=duration,start=start,note='ภาพจากช็อตพื้นฐานช่วงซับนี้ ไม่ข้ามรอยตัด ไม่รวมเอฟเฟกต์เดิมและมิกซ์เสียง · '+('เสียงเฉพาะไฟล์ภาพต้นฉบับ (ถ้ามี)' if audible else 'ปิดเสียงพรีวิวช่วงนี้')+' · สูงสุด 12 วินาที')
        except BaseException:
            if folder:shutil.rmtree(folder,ignore_errors=True)
            raise
        finally:_render_lock.release()
    raise ValueError('คำสั่งสตูดิโอซับไม่ถูกต้อง')
