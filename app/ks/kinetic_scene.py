"""Opt-in scene geometry shared by native copies and web playback. No face inference."""
import copy,uuid,math
FRAMINGS=('keep','speaker_left')
MOVES=('static','push','pull','smooth_in','smooth_out','smooth_in_out','snap_in','snap_out','snap_in_out','snap_to_cut','cinematic')
JOIN_GAP=.75

DEFAULT_COMPOSITION=dict(video_x=-.06,video_y=0,video_scale=1.08,text_x=.51,text_y=.32)
def composition(raw=None):
 if raw is None:raw={}
 if not isinstance(raw,dict) or set(raw)-set(DEFAULT_COMPOSITION):raise ValueError('ค่าจัดองค์ประกอบไม่ถูกต้อง')
 result=dict(DEFAULT_COMPOSITION,**raw)
 bounds=dict(video_x=(-.6,0),video_y=(-.12,.12),video_scale=(1,1.2),text_x=(-.55,.55),text_y=(.15,.5))
 for k,v in result.items():
  if type(v) not in (int,float) or not math.isfinite(v) or not bounds[k][0]<=v<=bounds[k][1]:raise ValueError('ค่าจัดองค์ประกอบอยู่นอกช่วงที่รองรับ')
 return result

def cut_end(draft,start):
 if not isinstance(draft,dict):raise ValueError('ซูมถึงคัทต้องอ่านช็อตต้นฉบับก่อน')
 tracks=[t for t in draft.get('tracks',[]) if t.get('type')=='video' and not t.get('attribute',0)&1]
 if len(tracks)!=1:raise ValueError('ซูมถึงคัทรองรับภาพหลักหนึ่งแทร็ก')
 matches=[]
 for seg in tracks[0].get('segments',[]):
  tr=seg.get('target_timerange') or {};a=tr.get('start',0)/1e6;b=a+tr.get('duration',0)/1e6
  if a<=start<b:matches.append(b)
 if len(matches)!=1:raise ValueError('ไม่พบช็อตหลักที่แน่นอนสำหรับซูมถึงคัท')
 return matches[0]

def scenes(blocks,draft=None):
 result=[];join=False
 for b in blocks:
  framing=b.get('framing','keep');move=b.get('camera_move','static')
  if framing not in FRAMINGS or move not in MOVES:raise ValueError('การจัดภาพไม่ถูกต้อง')
  if not b.get('enabled',True) or (framing=='keep' and not (move.startswith('snap_') or move=='cinematic')):join=False;continue
  geom=composition(b.get('composition'))
  if move.startswith(('smooth_','snap_')) or move=='cinematic':geom.update(video_x=0,video_y=0,video_scale=1)
  if move=='static' and geom['video_x']==0 and geom['video_y']==0 and geom['video_scale']==1:join=False;continue
  start=min(u['start'] for u in b['units']);end=max(u['end'] for u in b['units'])
  if move=='snap_to_cut':end=cut_end(draft,start)
  if move!='cinematic' and not move.startswith(('smooth_','snap_')) and join and result and start-result[-1]['end']<=JOIN_GAP and move==result[-1]['move'] and geom==result[-1]['composition']:result[-1]['end']=end
  else:result.append(dict(start=start,end=end,move=move,composition=geom,x=geom['video_x'],y=geom['video_y'],scale_from=geom['video_scale']+.05 if move=='pull' else geom['video_scale'],scale_to=geom['video_scale']+.05 if move=='push' else geom['video_scale']))
  join=True
 if any(s['move']=='snap_to_cut' for s in result):
  resolved=[]
  for scene in sorted(result,key=lambda s:s['start']):
   if resolved and resolved[-1]['move']=='snap_to_cut' and scene['start']<resolved[-1]['end']:
    if scene['move']=='snap_to_cut':continue
    resolved[-1]['end']=scene['start']
   resolved.append(scene)
  result=resolved
 for scene in result:
  if scene['move'].startswith('snap_'):
   start,end=scene['start'],scene['end'];ramp=min(.30,(end-start)/3);mode=scene['move']
   # Include every ramp boundary explicitly: web and native interpolate these knots.
   points=[]
   for i in range(21):
    u=i/20;ease=u*u*(3-2*u)
    points.append([start+ramp*u,1.3-.3*ease if mode=='snap_out' else 1+.3*ease])
   if mode=='snap_in_out':
    points.append([end-ramp,1.3])
    for i in range(1,21):
     u=i/20;ease=u*u*(3-2*u)
     points.append([end-ramp+ramp*u,1.3-.3*ease])
   else:points.append([end,1 if mode=='snap_out' else 1.3])
   scene.update(scale_points=points,scale_from=points[0][1],scale_to=points[-1][1])
  if scene['move'].startswith('smooth_') or scene['move']=='cinematic':
   mode=scene['move'];points=[]
   for i in range(41):
    u=i/40
    if mode=='smooth_in_out':u=2*u if u<=.5 else 2*(1-u)
    ease=u*u*(3-2*u)
    value=1.3-.3*ease if mode=='smooth_out' else 1+(.05 if mode=='cinematic' else .3)*ease
    points.append([scene['start']+(scene['end']-scene['start'])*i/40,value])
   scene.update(scale_points=points,scale_from=points[0][1],scale_to=points[-1][1])
 return result

def frame(scene,time):
 u=max(0,min(1,(time-scene['start'])/(scene['end']-scene['start'])))
 scale=scene['scale_from']+(scene['scale_to']-scene['scale_from'])*u
 points=scene.get('scale_points')
 if points:
  at=max(scene['start'],min(scene['end'],time))
  for (a,av),(b,bv) in zip(points,points[1:]):
   if at<=b:
    scale=av+(bv-av)*(at-a)/(b-a);break
 return dict(x=scene['x'],y=scene['y'],scale=scale)

def apply(draft,scenes):
 out=copy.deepcopy(draft)
 if not scenes:return out
 for scene in scenes:
  if min(scene['scale_from'],scene['scale_to'])+1e-7<1+max(abs(scene['x']),abs(scene['y'])):raise ValueError('การเลื่อนภาพทำให้ขอบภาพขาด กรุณาลดการเลื่อนหรือคงภาพเดิม')
 from .cli_lab_social import curve
 _validate_base(out)
 videos=[t for t in out.get('tracks',[]) if t.get('type')=='video' and not t.get('attribute',0)&1]
 if len(videos)!=1:raise ValueError('โหมดจัดฉากยังรองรับภาพหลักหนึ่งแทร็ก กรุณาคงภาพเดิมสำหรับโปรเจกต์ที่มีภาพซ้อน')
 track=videos[0];result=[]
 for original in track['segments']:
  tr=original['target_timerange'];a=tr['start']/1e6;b=(tr['start']+tr['duration'])/1e6
  overlaps=[c for c in scenes if c['start']<b and c['end']>a]
  if not overlaps:result.append(original);continue
  clip=original.get('clip') or {};scale=clip.get('scale') or {};pos=clip.get('transform') or {};speed=original.get('speed',1)
  if (type(speed) not in (int,float) or not math.isfinite(speed) or not .125<=speed<=8 or original.get('reverse') or original.get('is_reverse') or original.get('common_keyframes') or original.get('keyframe_refs') or clip.get('rotation',0) or any((clip.get('flip') or {}).values()) or any(abs(scale.get(k,1)-1)>1e-6 or abs(pos.get(k,0))>1e-6 for k in ('x','y'))):raise ValueError('ภาพมีครอป/การเคลื่อนชั้นนอกอยู่แล้ว กรุณาคงภาพเดิมเพื่อรักษางานเดิม')
  source=original.get('source_timerange')
  if not source:raise ValueError('อ่านช่วงภาพต้นฉบับไม่ได้')
  # CapCut stores integer microseconds; coalesce equivalent float endpoints before splitting.
  edges=sorted({round(t*1e6)/1e6 for t in [a,b,*[max(a,c['start']) for c in overlaps],*[min(b,c['end']) for c in overlaps]]})
  for left,right in zip(edges,edges[1:]):
   seg=copy.deepcopy(original);seg['id']=uuid.uuid4().hex;seg['target_timerange']=dict(start=round(left*1e6),duration=round(right*1e6)-round(left*1e6));src=source['start']+round((left-a)*speed*1e6);finish=source['start']+round((right-a)*speed*1e6);seg['source_timerange']=dict(start=src,duration=finish-src)
   scene=next((c for c in overlaps if c['start']<=left+1e-7<c['end']),None)
   if scene:
    first,last=frame(scene,left),frame(scene,right);seg['clip']=dict(clip,scale=dict(x=first['scale'],y=first['scale']),transform=dict(x=first['x'],y=first['y']))
    points=[(0,first['scale'])]+[(t-left,v) for t,v in scene.get('scale_points',[]) if left<t<right]+[(right-left,last['scale'])]
    for axis in ('X','Y'):curve(seg,'KFTypeScale'+axis,points,source=True)
    for axis in ('X','Y'):curve(seg,'KFTypePosition'+axis,[(0,first[axis.lower()]),(right-left,last[axis.lower()])],source=True)
   result.append(seg)
 track['segments']=result
 return out


def _validate_base(draft,selected=None,depth=0):
 if depth>8:raise ValueError('ภาพซ้อนลึกเกินไป')
 materials={m['id']:m for m in draft.get('materials',{}).get('videos',[])}
 nested={m['id']:m['draft'] for m in draft.get('materials',{}).get('drafts',[]) if isinstance(m.get('draft'),dict)}
 speeds={m['id']:m for m in draft.get('materials',{}).get('speeds',[])}
 unsafe={m['id'] for kind in ('audio_fades','transitions','material_animations') for m in draft.get('materials',{}).get(kind,[]) if kind!='material_animations' or m.get('animations')}
 for track in draft.get('tracks',[]):
  if track.get('type')!='video' or (selected and track.get('id')!=selected):continue
  for seg in track.get('segments',[]):
   mat=materials.get(seg.get('material_id'),{});crop=mat.get('crop') or {}
   if any(abs(v-(1 if ('right_x' in k or 'lower_' in k and k.endswith('_y')) else 0))>1e-6 for k,v in crop.items()):raise ValueError('กล้องมีครอปฐานที่พรีวิวยังจำลองไม่ได้ กรุณาคงภาพเดิม')
   refs=seg.get('extra_material_refs',[])
   if seg.get('reverse') or seg.get('is_reverse'):raise ValueError('ภาพเล่นย้อนกลับ กรุณาคงภาพเดิม')
   if not depth and any(r in unsafe for r in refs):raise ValueError('ภาพมี fade/transition/animation ที่ต้องรักษาที่ขอบเดิม กรุณาคงภาพเดิม')
   if any(speeds.get(r,{}).get('curve_speed') for r in refs):raise ValueError('ภาพมีกราฟความเร็ว กรุณาคงภาพเดิม')
   children=[nested[r] for r in refs if r in nested]
   if children:
    chosen=(mat.get('multi_camera_info') or {}).get('cur_camera_track_id')
    if len(children)!=1 or not chosen:raise ValueError('compound นี้ยังจัดฉากไม่ได้ กรุณาคงภาพเดิม')
    _validate_base(children[0],chosen,depth+1)
   if depth:
    clip=seg.get('clip') or {}
    if seg.get('common_keyframes') or any(abs((clip.get('scale') or {}).get(k,1)-1)>1e-6 or abs((clip.get('transform') or {}).get(k,0))>1e-6 for k in ('x','y')) or clip.get('rotation',0) or any((clip.get('flip') or {}).values()):raise ValueError('กล้องย่อยมีการจัดกรอบที่พรีวิวยังจำลองไม่ได้ กรุณาคงภาพเดิม')
