"""Conservative selected-camera sampling for local, reviewable framing suggestions."""
import math,statistics,tempfile,subprocess,copy
from pathlib import Path

def propose(samples):
 if len(samples)<3 or any(len(f)!=1 for f in samples):return None
 faces=[s[0] for s in samples]
 for f in faces:
  if set(f)!={'x','y','width','height','confidence'} or any(type(v) not in (int,float) or not math.isfinite(v) for v in f.values()) or f['confidence']<.8 or not .03<=f['width']<=.35 or not .05<=f['height']<=.45 or not 0<=f['x']<f['x']+f['width']<=1 or not 0<=f['y']<f['y']+f['height']<=1:return None
 centers=[(f['x']+f['width']/2,f['y']+f['height']/2) for f in faces]
 if max(c[0] for c in centers)-min(c[0] for c in centers)>.06 or max(c[1] for c in centers)-min(c[1] for c in centers)>.06:return None
 # Reserve a full side lane including entrance/outline padding. Try the
 # original picture first; never create negative space by shifting the camera.
 if all(f['x']+f['width']+.02<=.57 for f in faces):anchor=.51
 elif all(f['x']-.02>=.43 for f in faces):anchor=-.51
 else:return None
 return dict(video_x=0,video_y=0,video_scale=1,text_x=anchor,text_y=.5)

def sample_geometry(canvas):
 w=canvas.get('width',1920);h=canvas.get('height',1080)
 if type(w) not in (int,float) or type(h) not in (int,float) or not all(math.isfinite(v) and 0<v<=16384 for v in (w,h)):raise ValueError('ขนาด canvas ไม่ถูกต้อง')
 scale=min(960/w,540/h);pw=max(2,int(w*scale)//2*2);ph=max(2,int(h*scale)//2*2)
 return pw,ph,f'scale={pw}:{ph}:force_original_aspect_ratio=decrease,pad={pw}:{ph}:(ow-iw)/2:(oh-ih)/2'

def _observe(source,time,binary,image_filter,target):
 """Extract one canvas-aligned frame; failed detectors never become empty evidence."""
 from .face_rectangles import detect,detect_hands
 if source.get('photo'):return dict(faces=[],hands=[],complete=False)
 r=subprocess.run([binary,'-nostdin','-v','error','-y','-ss',str(source['offset']),'-i',source['path'],'-frames:v','1','-vf',image_filter,str(target)],capture_output=True,timeout=45)
 if r.returncode:return dict(faces=[],hands=[],complete=False)
 try:return dict(faces=detect(target),hands=detect_hands(target),complete=True)
 except (ValueError,OSError,AttributeError):return dict(faces=[],hands=[],complete=False)


def assist(draft,plan,project,progress=lambda message:None,settings=None,allow_motion_fallback=False):
 """Try identity-video text anchors against bounded rendered motion evidence."""
 from . import kinetic_scene as SC,caption_studio as S,core_engine as CE,kinetic_text as K,placement_review as PR
 from .cli_lab_story import resolve_media_paths
 SC._validate_base(draft)
 out=copy.deepcopy(plan);d=resolve_media_paths(draft,project);binary=CE.ac_ffmpeg_bin()
 if not binary:raise ValueError('ไม่พบเครื่องมืออ่านภาพ')
 settings=dict(settings or {})
 if not settings.get('font'):
  from .cli_lab_typography import editorial_font
  settings['font']=editorial_font() or ''
 blocks=[b for b in out['blocks'] if b.get('enabled',True)]
 if len(blocks)>60:raise ValueError('ช่วยจัดกรอบได้สูงสุด60ชุดต่อครั้ง กรุณาซ่อนชุดที่ไม่เน้นก่อน')
 canvas=draft.get('canvas_config') or {};_,_,image_filter=sample_geometry(canvas)
 # Include original edit boundaries, even when two shots use the same file.
 cuts=[]
 for track in d.get('tracks',[]):
  if track.get('type')=='video' and not track.get('attribute',0)&1:
   for segment in track.get('segments',[]):
    tr=segment.get('target_timerange') or {};a=tr.get('start',0)/1e6
    cuts.extend((a,a+tr.get('duration',0)/1e6))
 cache={};accepted=0;records=[];motion_adjustments=0
 with tempfile.TemporaryDirectory(prefix='chuaydai-framing-') as folder:
  for index,block in enumerate(out['blocks']):
   if not block.get('enabled',True):continue
   progress('ตรวจภาพและมือในเครื่อง '+str(len(records)+1)+'/'+str(len(blocks))+' · ไม่ส่งคลิปออกภายนอก')
   record=dict(cue_id=block['cue_id'],safe=False,reasons=[],checked_samples=0)
   start=min(u['start'] for u in block['units']);end=max(u['end'] for u in block['units']);record['interval']=[start,end]
   observed={};chosen=None;original_motion=[]
   anchors=[(.51,.5,False),(-.51,.5,False),(.51,.35,False),(-.51,.35,False)]
   for attempt,(x,y,static_fallback) in enumerate(anchors):
    candidate=copy.deepcopy(out)
    candidate['blocks'][index].update(framing='speaker_left',composition=dict(video_x=0,video_y=0,video_scale=1,text_x=x,text_y=y))
    if static_fallback:candidate['blocks'][index]['camera_move']='static'
    try:
     _,preview=K.render(d,candidate,**settings)
     entries=[e for e in preview['entries'] if e['cue_id']==block['cue_id']]
     if not entries:raise ValueError('no rendered text for cue')
     scenes=list(preview.get('scenes',[]))
     if not static_fallback:
      original_motion=[s for s in scenes if any(s['start']<e['end'] and s['end']>e['start'] for e in entries)]
     else:
      # Removing zoom must still review the original held interval at identity.
      # Other overlapping scenes fail closed rather than hiding their geometry.
      scenes += [dict(s,x=0,y=0,scale_from=1,scale_to=1,scale_points=[]) for s in original_motion]
     intervals=[PR.motion_interval(e['start'],e['end'],scenes) for e in entries]
     coverage_end=max(b for a,b in intervals)
     record['text_interval']=[start,end];record['interval']=[min(a for a,b in intervals),coverage_end]
     times=sorted({t for a,b in intervals for t in PR.sample_schedule(a,b,scenes,cuts)})
     if len(times)>240:raise ValueError('placement sampling exceeds 240 samples')
     observations=[]
     for time in times:
      if time not in observed and len(observed)>=240:raise ValueError('placement sampling exceeds 240 samples')
      # Endpoints describe the visible left limit of an exclusive text interval.
      at=time-1e-6 if abs(time-coverage_end)<1e-7 else time
      source=S.source_at(d,at)
      speed=source.get('speed',1)
      camera=(source['path'],speed,round(source['offset']-at*speed,4))
      key=(round(at,7),camera)
      if key not in cache:
       progress('ตรวจภาพและมือในเครื่อง · '+str(round(time,2))+' วินาที')
       cache[key]=_observe(source,time,binary,image_filter,Path(folder)/('frame-'+str(len(cache))+'.jpg'))
      observation=dict(cache[key],time=time,camera=repr(camera));observations.append(observation);observed[time]=observation
     result=PR.review(entries,scenes,observations,canvas,settings['font'])
     record['checked_samples']=max(record['checked_samples'],result['checked_samples'])
     if result['safe']:
      chosen=candidate;record.update(safe=True,reasons=[])
      if static_fallback:
       record['motion_adjusted_from']=block.get('camera_move','static');motion_adjustments+=1
      break
     for reason in result['reasons']:
      if reason not in record['reasons']:record['reasons'].append(reason)
    except (ValueError,OSError,KeyError,TypeError,subprocess.TimeoutExpired) as exc:
     reason='unsupported placement evidence: '+str(exc)
     if reason not in record['reasons']:record['reasons'].append(reason)
    if attempt==3 and allow_motion_fallback is True and block.get('camera_move','static')!='static' and 'face extends outside canvas during motion' in record['reasons']:
     anchors.extend((a,b,True) for a,b in ((.51,.5),(-.51,.5),(.51,.35),(-.51,.35)))
   record['sample_count']=len(observed);records.append(record)
   if chosen is not None:out=chosen;accepted+=1
 return out,dict(method='local_face_hand_rendered_motion_samples',accepted=accepted,uncertain=len(blocks)-accepted,motion_adjustments=motion_adjustments,records=records,note='ตรวจขอบข้อความจริงพร้อมซูม ใบหน้าและมือเฉพาะเฟรมตัวอย่างที่ระบุ · ปรับซูมเฉพาะเมื่อเปิดให้พักซูมที่ตัดใบหน้า พร้อมบันทึกเหตุผล ไม่ใช่การติดตามทุกเฟรมหรือการรับรองทั้งช็อต')


def _groups(records):
 """Share one pose while adjacent selected-camera evidence remains consistent."""
 from .kinetic_scene import JOIN_GAP
 groups=[];previous=None
 for record in records:
  if not record['proposed']:previous=None;continue
  group=groups[-1] if previous and groups else None
  shared=propose(group['samples']+record['samples']) if group and previous['index']+1==record['index'] and record['start']-previous['end']<=JOIN_GAP and record['camera']==previous['camera'] else None
  if shared:
   group['records'].append(record);group['samples']+=record['samples'];group['composition']=shared
  else:groups.append(dict(records=[record],samples=list(record['samples']),composition=record['proposed']))
  previous=record
 return groups
