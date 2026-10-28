"""One history for new checkpoints and older subtitle/clip backups."""
import hashlib,json,os,time
from pathlib import Path
from . import event_timeline as T,event_clip as E

LABELS={'before_proofread':'ก่อนแก้คำในซับ / Super Text','before_apply':'ก่อนสร้างซับ / Super Text','before_cut':'ก่อนตัดคลิป','before_restore':'ก่อนกู้คืน',
 'before_cli_replace':'ก่อนใช้ผล CLI กับโปรเจกต์เดิม',
 'before_resegment':'ก่อนแบ่งซับ','before_audio_align':'ก่อนจับจังหวะจากเสียง','before_caption_style':'ก่อนปรับฟอนต์ / ขนาด',
 'before_caption_repair':'ก่อนซ่อมซับ','before_caption_restore':'ก่อนคืนรูปแบบซับ','manual':'บันทึกจุดกู้คืนเอง',
 'before_restore_snap':'ก่อนกู้คืน','before_snap_restore':'ก่อนกู้คืน','checkpoint':'บันทึกจุดกู้คืนเอง'}

def digest(raw):return hashlib.sha1(raw).hexdigest()
def listing(proj):
 from . import core_engine as C
 root=Path(proj);rows=[]
 for r in T.list_backups(proj)['backups']:
  rows.append({'id':'checkpoint:'+r['name'],'created':r['created'],'title':LABELS.get(r['label'],'จุดกู้คืนอัตโนมัติ'),'kind':'checkpoint'})
 for r in C.list_snapshots(proj):
  rows.append({'id':'snapshot:'+r['name'],'created':r['mtime'],'title':LABELS.get(r.get('label'),'ประวัติซับจากระบบเดิม'),'kind':'snapshot'})
 for p in (root/'.autoclip_backups').glob('*'):
  if p.is_dir() and (p/'draft_info.json').is_file():rows.append({'id':'autoclip:'+p.name,'created':p.stat().st_mtime,'title':'ก่อนตัดคลิปจากระบบเดิม','kind':'autoclip'})
 if (root/'draft_info_backup.json').is_file():rows.append({'id':'initial:original','created':(root/'draft_info_backup.json').stat().st_mtime,'title':'จุดเริ่มต้นก่อนใช้เครื่องมือ','kind':'initial'})
 rows.sort(key=lambda x:x['created'],reverse=True)
 return {'ok':True,'items':rows,'source_hash':digest((root/'draft_info.json').read_bytes()),'source_project':os.path.realpath(proj),'last_clear':latest_clear(proj)}

def checkpoint(proj,cfg=None):
 cfg=cfg or {};T.ensure_closed();root=Path(proj)
 if cfg.get('source_project') and os.path.realpath(proj)!=os.path.realpath(cfg['source_project']):raise ValueError('โปรเจกต์เปลี่ยนแล้ว กรุณาโหลดสถานะล่าสุด')
 raw=(root/'draft_info.json').read_bytes()
 if cfg.get('source_hash') and digest(raw)!=cfg['source_hash']:raise ValueError('ไทม์ไลน์เปลี่ยนแล้ว กรุณาโหลดสถานะล่าสุดก่อนบันทึกจุดกู้คืน')
 E.progress(message='กำลังบันทึกจุดกู้คืน',commit_started=True)
 p=T.checkpoint(proj,'manual')
 if T.read_checkpoint(proj,p.name)['draft_info.json']!=raw or (root/'draft_info.json').read_bytes()!=raw:raise ValueError('ไทม์ไลน์เปลี่ยนระหว่างสำรอง กรุณาบันทึกใหม่')
 return {'ok':True,'backup_name':p.name,'msg':'บันทึกจุดกู้คืนแล้ว','history':listing(proj)}

def commit_draft(proj,draft,expected_raw,label):
 """Commit current draft and its mirror, keeping every prior file recoverable."""
 from .apply_guard import project_lock
 with project_lock(proj):
  T.ensure_closed();root=Path(proj);src=root/'draft_info.json';main=T.target_path(proj,'__project_draft_info.json')
  parent=main.read_bytes() if main is not None and main.is_file() else None
  if src.read_bytes()!=expected_raw:raise ValueError('ไทม์ไลน์เปลี่ยนระหว่างทำงาน ยังไม่ได้เขียนผล กรุณาโหลดซับล่าสุด')
  if parent is not None and json.loads(parent).get('id')!=draft.get('id'):raise ValueError('กรุณาเลือกไทม์ไลน์หลักล่าสุดก่อนแก้ไข')
  E.progress(message='กำลังสำรองและบันทึกผล',commit_started=True)
  backup=T.checkpoint(proj,label);old=T.read_checkpoint(proj,backup.name)
  if src.read_bytes()!=expected_raw or old['draft_info.json']!=expected_raw or (parent is not None and main.read_bytes()!=parent):raise ValueError('ไฟล์เปลี่ยนระหว่างสำรอง ยังไม่ได้บันทึกผล')
  data=json.dumps(draft,ensure_ascii=False).encode();updates={'draft_info.json':data,'draft_info_original.json':None,'.spinworld_state.json':None}
  if old['draft_info_backup.json'] is None:updates['draft_info_backup.json']=expected_raw
  if parent is not None:updates['__project_draft_info.json']=data
  for key in ('draft_meta_info.json','__project_draft_meta_info.json'):
   if old[key] is not None:
    meta=json.loads(old[key]);meta.update(tm_duration=draft.get('duration') or max((int(s.get('target_timerange',{}).get('start',0))+int(s.get('target_timerange',{}).get('duration',0)) for t in draft.get('tracks',[]) for s in t.get('segments',[])),default=0),tm_draft_modified=int(time.time()*1e6));updates[key]=json.dumps(meta,ensure_ascii=False).encode()
  T.ensure_closed()
  try:T.replace_files(proj,updates)
  except Exception:T.replace_files(proj,{k:old[k] for k in updates});raise
  return backup.name

def _legacy_draft(proj,kind,name):
 root=Path(proj)
 if not name or Path(name).name!=name:raise ValueError('ชื่อจุดกู้คืนไม่ถูกต้อง')
 if kind=='snapshot':p=root/'.karaoke_snapshots'/name
 elif kind=='autoclip':p=root/'.autoclip_backups'/name/'draft_info.json'
 elif kind=='initial' and name=='original':p=root/'draft_info_backup.json'
 else:raise ValueError('จุดกู้คืนไม่ถูกต้อง')
 if not p.is_file():raise ValueError('ไม่พบจุดกู้คืนนี้')
 return json.loads(p.read_bytes())

def restore(proj,cfg):
 from .apply_guard import project_lock
 with project_lock(proj):
  T.ensure_closed();root=Path(proj);raw=(root/'draft_info.json').read_bytes()
  if cfg.get('source_project') and os.path.realpath(proj)!=os.path.realpath(cfg['source_project']):raise ValueError('โปรเจกต์เปลี่ยนแล้ว กรุณาโหลดรายการกู้คืนใหม่')
  if cfg.get('source_hash') and digest(raw)!=cfg['source_hash']:raise ValueError('ไทม์ไลน์เปลี่ยนแล้ว กรุณาโหลดรายการกู้คืนใหม่')
  parts=str(cfg.get('id','')).split(':',1)
  if len(parts)!=2:raise ValueError('กรุณาเลือกจุดกู้คืน')
  kind,name=parts
  if kind!='checkpoint':
   d=_legacy_draft(proj,kind,name)
   if d.get('id')!=json.loads(raw).get('id'):raise ValueError('จุดกู้คืนนี้เป็นของไทม์ไลน์อื่น')
   backup=commit_draft(proj,d,raw,'before_restore')
  else:
   previous=T.read_checkpoint(proj,name)
   if json.loads(previous['draft_info.json']).get('id')!=json.loads(raw).get('id'):raise ValueError('จุดกู้คืนนี้เป็นของไทม์ไลน์อื่น')
   parent=T.target_path(proj,'__project_draft_info.json')
   parent_raw=parent.read_bytes() if parent is not None and parent.is_file() else None
   if parent is not None and parent.is_file() and json.loads(parent.read_bytes()).get('id')!=json.loads(raw).get('id'):raise ValueError('กรุณาเลือกไทม์ไลน์หลักล่าสุดก่อนกู้คืน')
   E.progress(message='กำลังสำรองก่อนกู้คืน',commit_started=True)
   safety=T.checkpoint(proj,'before_restore');current=T.read_checkpoint(proj,safety.name)
   if (root/'draft_info.json').read_bytes()!=raw or current['draft_info.json']!=raw or (parent_raw is not None and (current['__project_draft_info.json']!=parent_raw or parent.read_bytes()!=parent_raw)):raise ValueError('ไทม์ไลน์เปลี่ยนระหว่างสำรอง ยังไม่ได้กู้คืน')
   # A checkpoint without a mirror still restores the live mirror consistently.
   if parent is not None and parent.is_file() and previous['__project_draft_info.json'] is None:previous['__project_draft_info.json']=previous['draft_info.json']
   T.ensure_closed()
   try:T.replace_files(proj,previous)
   except Exception:T.replace_files(proj,current);raise
   backup=safety.name
  return {'ok':True,'msg':'กู้คืนแล้ว และเก็บจุดสำรองก่อนกู้คืนไว้ให้','message':'กู้คืนแล้ว เปิด CapCut เพื่อตรวจ','backup_name':backup,'history':listing(proj)}

# Clearing history never removes the live draft, caption baseline, or initial backup.
HISTORY_DIRS=('.event_timeline_backups','.karaoke_snapshots','.autoclip_backups')
ARCHIVE_DIR='.history_archives'

def _history_request(proj,cfg):
 root=Path(proj)
 if cfg.get('source_project')!=os.path.realpath(proj):raise ValueError('โปรเจกต์เปลี่ยนแล้ว กรุณาเปิดประวัติใหม่')
 if cfg.get('source_hash')!=digest((root/'draft_info.json').read_bytes()):raise ValueError('ไทม์ไลน์เปลี่ยนแล้ว กรุณาเปิดประวัติใหม่')
 archive=root/ARCHIVE_DIR
 if archive.is_symlink():raise ValueError('โฟลเดอร์ประวัติเป็นลิงก์ ไม่ดำเนินการ')
 for name in HISTORY_DIRS:
  if (root/name).is_symlink():raise ValueError('โฟลเดอร์ประวัติเป็นลิงก์ ไม่ดำเนินการ')
 return root,archive

def latest_clear(proj):
 archive=Path(proj)/ARCHIVE_DIR;rows=[]
 if archive.is_symlink():return None
 for p in archive.glob('*/manifest.json'):
  try:
   if p.parent.is_symlink() or p.is_symlink():continue
   m=json.loads(p.read_bytes())
   if m.get('project')==os.path.realpath(proj) and m.get('state') in ('cleared','clearing'):
    rows.append({'id':p.parent.name,'created':m['created'],'count':m.get('count',0)})
  except (OSError,ValueError,KeyError):pass
 return max(rows,key=lambda r:r['created'],default=None)

def clear(proj,cfg):
 import uuid
 from .apply_guard import project_lock
 with project_lock(proj):
  root,archive=_history_request(proj,cfg)
  folders=[name for name in HISTORY_DIRS if (root/name).is_dir()]
  count=sum(r['kind']!='initial' for r in listing(proj)['items'])
  if not folders:return {'ok':True,'msg':'ไม่มีประวัติสะสมให้ล้าง','removed':0,'history':listing(proj)}
  archive.mkdir(exist_ok=True)
  box=archive/(time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]);box.mkdir()
  manifest={'project':os.path.realpath(proj),'created':time.time(),'state':'clearing','folders':folders,'count':count}
  T.atomic_write(box/'manifest.json',json.dumps(manifest).encode())
  E.progress(message='กำลังจัดเก็บประวัติเก่า คงจุดเริ่มต้นและไฟล์งานไว้',commit_started=True)
  moved=[]
  try:
   for name in folders:
    os.replace(root/name,box/name);moved.append(name)
   manifest['state']='cleared';T.atomic_write(box/'manifest.json',json.dumps(manifest).encode())
  except Exception:
   for name in reversed(moved):os.replace(box/name,root/name)
   manifest['state']='rolled_back';T.atomic_write(box/'manifest.json',json.dumps(manifest).encode());raise
  return {'ok':True,'msg':f'ล้างประวัติ {count} จุดแล้ว คงจุดเริ่มต้นไว้ และยกเลิกการล้างได้','removed':count,'archive_id':box.name,'history':listing(proj)}

def undo_clear(proj,cfg):
 from .apply_guard import project_lock
 with project_lock(proj):
  root,archive=_history_request(proj,cfg);name=cfg.get('archive_id')
  if not isinstance(name,str) or not name or Path(name).name!=name:raise ValueError('ชื่อชุดประวัติไม่ถูกต้อง')
  box=archive/name
  if box.is_symlink() or (box/'manifest.json').is_symlink():raise ValueError('โฟลเดอร์ประวัติเป็นลิงก์ ไม่ดำเนินการ')
  m=json.loads((box/'manifest.json').read_bytes())
  if m.get('project')!=os.path.realpath(proj) or m.get('state') not in ('cleared','clearing'):raise ValueError('ไม่พบประวัติที่ยกเลิกการล้างได้')
  if not isinstance(m.get('folders'),list) or set(m['folders'])-set(HISTORY_DIRS):raise ValueError('ข้อมูลชุดประวัติไม่ถูกต้อง')
  moves=[];created=[]
  # Preflight every collision before moving anything; preserve newly created history.
  for folder in m['folders']:
   src=box/folder;dst=root/folder
   if src.is_symlink():raise ValueError('โฟลเดอร์ประวัติเป็นลิงก์ ไม่ดำเนินการ')
   if not src.is_dir():continue
   if dst.exists() and not dst.is_dir():raise ValueError('ตำแหน่งประวัติไม่ใช่โฟลเดอร์')
   for p in src.iterdir():
    target=dst/p.name
    if target.exists() or target.is_symlink():raise ValueError('ชื่อประวัติชนกับประวัติใหม่ ยังไม่ได้ย้ายประวัติใด')
    moves.append((p,target))
  E.progress(message='กำลังคืนรายการประวัติที่ล้าง ไม่แก้ไฟล์ไทม์ไลน์',commit_started=True)
  moved=[]
  try:
   for src,dst in moves:
    if not dst.parent.exists():dst.parent.mkdir();created.append(dst.parent)
    os.replace(src,dst);moved.append((src,dst))
   m['state']='restored';T.atomic_write(box/'manifest.json',json.dumps(m).encode())
  except Exception:
   for src,dst in reversed(moved):os.replace(dst,src)
   for p in reversed(created):p.rmdir()
   raise
  return {'ok':True,'msg':'ยกเลิกการล้างแล้ว คืนรายการประวัติให้ครบ โดยคงงานปัจจุบันไว้','history':listing(proj)}
