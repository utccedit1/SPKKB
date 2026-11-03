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

def assist(draft,plan,project,progress=lambda message:None):
 from . import kinetic_scene as SC,caption_studio as S,core_engine as CE
 from .cli_lab_story import resolve_media_paths
 from .face_rectangles import detect
 SC._validate_base(draft)
 out=copy.deepcopy(plan);d=resolve_media_paths(draft,project);binary=CE.ac_ffmpeg_bin()
 if not binary:raise ValueError('ไม่พบเครื่องมืออ่านภาพ')
 blocks=[b for b in out['blocks'] if b.get('enabled',True)]
 if len(blocks)>60:raise ValueError('ช่วยจัดกรอบได้สูงสุด60ชุดต่อครั้ง กรุณาซ่อนชุดที่ไม่เน้นก่อน')
 _,_,image_filter=sample_geometry(draft.get('canvas_config') or {})
 accepted=0;records=[];processed=0
 with tempfile.TemporaryDirectory(prefix='chuaydai-framing-') as folder:
  for i,b in enumerate(out['blocks']):
   if not b.get('enabled',True):continue
   processed+=1
   progress('ตรวจภาพในเครื่อง '+str(processed)+'/'+str(len(blocks))+' · ไม่ส่งคลิปออกภายนอก')
   start=min(u['start'] for u in b['units']);end=max(u['end'] for u in b['units']);times=[start+(end-start)*f for f in (.08,.5,.92)];samples=[];camera_keys=[]
   for k,t in enumerate(times):
    source=S.source_at(d,t);camera_keys.append(source['path'])
    if source['photo']:samples=[];break
    target=Path(folder)/('sample-'+str(i)+'-'+str(k)+'.jpg')
    r=subprocess.run([binary,'-nostdin','-v','error','-y','-ss',str(source['offset']),'-i',source['path'],'-frames:v','1','-vf',image_filter,str(target)],capture_output=True,timeout=45)
    if r.returncode:raise ValueError('อ่านภาพตัวอย่างไม่ได้ กรุณาตรวจสื่อใน CapCut')
    samples.append(detect(target));progress('ตรวจภาพในเครื่อง '+str(processed)+'/'+str(len(blocks)))
   proposed=propose(samples)
   records.append(dict(block=b,index=i,start=start,end=end,samples=samples,camera=tuple(camera_keys),proposed=proposed))
 for group in _groups(records):
  for record in group['records']:
   record['block'].update(framing='speaker_left',camera_move='static',composition=group['composition']);accepted+=1
 return out,dict(method='local_face_rectangles_keep_picture',accepted=accepted,uncertain=len(blocks)-accepted,samples_per_beat=3,note='คงภาพเดิมและเสนอคำด้านข้างที่ว่าง · ตรวจเฉพาะสามเฟรมต่อชุด ไม่ใช่การติดตามทุกเฟรม/ตรวจมือหรือการยืนยันความปลอดภัยทั้งช็อต')


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
