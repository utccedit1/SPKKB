"""Long-running tasks use owned jobs, real stages, and one history."""
import hashlib,json,os,tempfile
from pathlib import Path
from . import core_engine as C,event_clip as E,event_timeline as T,unified_history as H

READ_TASKS={'suggest','caption','broll'}
WRITES={'generate','align','silence_apply','history_restore','history_checkpoint','history_clear','history_undo_clear'}
FEATURES={'suggest':'suggest','caption':'caption','broll':'broll','chatbot':'chatbot','align':'align','generate':'sfx','silence':'autoclip','sfx_listen':'align'}

def validate_source(proj,cfg):
 raw=(Path(proj)/'draft_info.json').read_bytes()
 if cfg.get('source_project') and os.path.realpath(proj)!=os.path.realpath(cfg['source_project']):raise ValueError('โปรเจกต์เปลี่ยนแล้ว กรุณาโหลดซับล่าสุด')
 if cfg.get('source_hash') and H.digest(raw)!=cfg['source_hash']:raise ValueError('ไทม์ไลน์เปลี่ยนแล้ว กรุณาโหลดซับล่าสุด')
 return raw

def media_stamp(path):
 p=Path(C.clean_fs_path(path))
 if not p.is_file():raise ValueError('ไม่พบไฟล์วิดีโอ กรุณาตรวจตำแหน่งไฟล์แล้ววางแผนใหม่')
 s=p.stat();return {'path':str(p.resolve()),'size':s.st_size,'mtime_ns':s.st_mtime_ns}

def safe_raw_cut(proj,cfg):
 from .apply_guard import project_lock
 with project_lock(proj):
  if not cfg.get('source_hash') or not cfg.get('video_stamp'):raise ValueError('กรุณาวางแผนตัดช่วงเงียบใหม่ก่อนตัดไทม์ไลน์')
  raw=validate_source(proj,cfg);d=json.loads(raw);video=C.clean_fs_path(cfg.get('video',''))
  if media_stamp(video)!=cfg['video_stamp']:raise ValueError('ไฟล์วิดีโอเปลี่ยนแล้ว กรุณาวางแผนใหม่')
  tracks=[tr for tr in d.get('tracks',[]) if tr.get('type')=='video' and tr.get('segments')]
  if len(tracks)!=1 or len(tracks[0]['segments'])!=1:raise ValueError('ตัดช่วงเงียบลงไทม์ไลน์ได้เมื่อมีวิดีโอต่อเนื่องหนึ่งชิ้น หากตัดต่อหลายชิ้นแล้วให้ส่งออก MP4 เพื่อตรวจแทน')
  seg=tracks[0]['segments'][0];mat=next((m for m in d.get('materials',{}).get('videos',[]) if m.get('id')==seg.get('material_id')),{});path=mat.get('path') or mat.get('material_path') or ''
  tr=seg.get('target_timerange') or {};sr=seg.get('source_timerange') or {}
  if os.path.realpath(C.clean_fs_path(path))!=os.path.realpath(video) or tr.get('start',0)!=0 or seg.get('speed',1)!=1:raise ValueError('ไฟล์วิดีโอไม่ตรงกับไทม์ไลน์ต่อเนื่องที่เลือก กรุณาส่งออก MP4 แทน เพื่อไม่ตัดผิดช่วง')
  offset=sr.get('start',0)/1e6;end=offset+tr.get('duration',0)/1e6
  windows=[[max(float(a),offset)-offset,min(float(b),end)-offset] for a,b in cfg.get('segments',[]) if min(float(b),end)>max(float(a),offset)]
  if not windows:raise ValueError('ไม่มีช่วงที่ตรงกับวิดีโอในไทม์ไลน์')
  return T.apply(proj,{'source_project':proj,'source_hash':hashlib.sha256(raw).hexdigest(),'segments':windows})

def run(proj,action,cfg):
 E.progress(message='กำลังตรวจข้อมูลล่าสุด',completed=0,total=0)
 if action=='sfx_listen':
  from . import sfx_library
  return sfx_library.analyze(cfg)
 # Chat has no dependency on the caption timeline.
 if action=='chatbot':
  from . import chatbot
  value=chatbot.api_chatbot(cfg,session_token=cfg.get('_session'))
  if isinstance(value,dict) and (value.get('error') or value.get('ok') is False):raise ValueError(value.get('error','งานไม่สำเร็จ'))
  return value
 raw=validate_source(proj,cfg)
 if action in READ_TASKS:
  captions=C.api_captions(proj,current=bool(cfg.get('caption_current')))
  if cfg.get('state_hash') and captions['state_hash']!=cfg['state_hash']:raise ValueError('รายการซับเปลี่ยนแล้ว กรุณาโหลดใหม่')
  source=Path(proj)/('draft_info_original.json' if captions['source']=='original' else 'draft_info.json')
  with tempfile.TemporaryDirectory(prefix='studio_ai_') as folder:
   (Path(folder)/'draft_info.json').write_bytes(source.read_bytes())
   result={'suggest':C.api_ai_suggest,'caption':C.api_ai_caption,'broll':C.api_broll if hasattr(C,'api_broll') else None}.get(action)
   if action=='broll':
    from . import broll
    result=broll.api_broll
   value=result(folder,cfg)
  if (Path(proj)/'draft_info.json').read_bytes()!=raw:raise ValueError('ไทม์ไลน์เปลี่ยนระหว่าง AI ทำงาน กรุณาโหลดซับใหม่ก่อนใช้คำแนะนำ')
 elif action=='chatbot':
  from . import chatbot
  value=chatbot.api_chatbot(cfg,session_token=cfg.get('_session'))
 elif action=='align':
  if not cfg.get('caption_current') or cfg.get('state_hash')!=H.digest(raw):raise ValueError('กรุณาโหลดซับจากไทม์ไลน์ล่าสุดและตรวจรายการก่อนจับจังหวะจากเสียง')
  value=C.api_ai_align_audio(proj,cfg)
 elif action=='generate':value=C.api_apply(proj,cfg)
 elif action=='silence':
  cfg=dict(cfg,mode='deadair');stamp=media_stamp(cfg.get('video',''));value=C.api_autoclip_plan(proj,cfg)
  if (Path(proj)/'draft_info.json').read_bytes()!=raw or media_stamp(cfg['video'])!=stamp:raise ValueError('ไทม์ไลน์หรือไฟล์วิดีโอเปลี่ยนระหว่างวางแผน กรุณาลองใหม่')
  if not value.get('error'):value.update(source_hash=H.digest(raw),source_project=os.path.realpath(proj),video_stamp=stamp)
 elif action=='silence_apply':
  value=safe_raw_cut(proj,cfg);value['msg']=value['message']
 elif action=='render':
  if cfg.get('video_stamp') and media_stamp(cfg.get('video',''))!=cfg['video_stamp']:raise ValueError('ไฟล์วิดีโอเปลี่ยนแล้ว กรุณาวางแผนใหม่')
  value=C.api_autoclip_render(proj,cfg)
 elif action=='history_restore':value=H.restore(proj,cfg)
 elif action=='history_checkpoint':value=H.checkpoint(proj,cfg)
 elif action=='history_clear':value=H.clear(proj,cfg)
 elif action=='history_undo_clear':value=H.undo_clear(proj,cfg)
 else:raise ValueError('งานไม่ถูกต้อง')
 E.progress(message='กำลังตรวจผลลัพธ์ก่อนส่งกลับ')
 if isinstance(value,dict) and (value.get('error') or value.get('ok') is False):raise ValueError(value.get('error','งานไม่สำเร็จ'))
 return value
