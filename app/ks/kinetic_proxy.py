"""Whole timeline base-picture/audio proxy; not a native effects composite."""
import math,shutil,subprocess,tempfile
from pathlib import Path
from . import caption_studio as S

def sources(draft):
 duration=draft.get('duration',0)/1e6
 if not 0<duration<=600:raise ValueError('พรีวิวทั้งคลิปได้ไม่เกิน 10 นาที')
 result=[];at=0.
 while at<duration-.000001:
  source=S.source_at(draft,at);span=min(duration-at,source['remaining'])
  if not math.isfinite(span) or span<=.000001:raise ValueError('อ่านขอบช็อตพรีวิวไม่ได้')
  result.append(dict(source,start=at,duration=span));at=round(at+span,6)
  if len(result)>400:raise ValueError('พรีวิวนี้มีช็อตมากเกินไป กรุณาตรวจใน CapCut')
 return result

def build(owner,workspace,project,raw,draft,media):
 from . import core_engine as CE
 from .cli_lab_story import resolve_media_paths
 from .cli_lab_alignment import render_speech
 if not S._render_lock.acquire(blocking=False):raise ValueError('กำลังสร้างพรีวิวอื่น กรุณารอสักครู่')
 folder=None
 try:
  d=resolve_media_paths(draft,project);parts=sources(d);binary=CE.ac_ffmpeg_bin()
  if not binary:raise ValueError('ไม่พบเครื่องมือพรีวิว')
  folder=Path(tempfile.mkdtemp(prefix='full-',dir=S._preview_temp.name));canvas=d.get('canvas_config') or {};w,h=canvas.get('width',1920),canvas.get('height',1080)
  if w<=0 or h<=0:raise ValueError('ขนาดภาพไม่ถูกต้อง')
  scale=min(960/w,540/h);pw=max(2,int(w*scale)//2*2);ph=max(2,int(h*scale)//2*2)
  def run(args):
   r=subprocess.run([binary,'-nostdin','-v','error','-y',*map(str,args)],capture_output=True,timeout=660)
   if r.returncode:raise ValueError('สร้างพรีวิวทั้งคลิปไม่ได้ กรุณาตรวจสื่อใน CapCut')
  paths=[]
  counts=frame_counts(parts)
  for i,p in enumerate(parts):
   if not counts[i]:continue
   out=folder/f'shot-{i:03}.mp4';args=['-loop','1'] if p['photo'] else ['-ss',p['offset']]
   args+=['-i',p['path'],'-frames:v',counts[i],'-an','-vf',f"setpts=(PTS-STARTPTS)/{p['speed']},scale={pw}:{ph}:force_original_aspect_ratio=decrease,pad={pw}:{ph}:(ow-iw)/2:(oh-ih)/2",'-r','30','-c:v','libx264','-preset','ultrafast','-crf','25','-pix_fmt','yuv420p',out];run(args);paths.append(out)
  (folder/'shots.txt').write_text(''.join("file '"+p.name+"'\n" for p in paths))
  audio=folder/'speech.wav';render_speech(d,audio,respect_volume=True)
  out=folder/'full.mp4';run(['-f','concat','-safe','0','-i',folder/'shots.txt','-i',audio,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-t',d['duration']/1e6,'-movflags','+faststart',out])
  S._read(project,S.fingerprint(raw))
  if S.media_fingerprint(draft,project)!=media:raise ValueError('สื่อเปลี่ยนระหว่างพรีวิว')
  token=S.register_asset(owner,workspace,project,out,S.fingerprint(raw))
  with S._guard:S._assets[token]['media_hash']=media
  return dict(ok=True,token=token,duration=d['duration']/1e6,note='ภาพกล้องที่เลือกและเสียงไทม์ไลน์ทั้งคลิป + ข้อความจำลอง ไม่รวมเอฟเฟกต์ภาพ/มิกซ์ทุกชนิดของ CapCut')
 except BaseException:
  if folder:shutil.rmtree(folder,ignore_errors=True)
  raise
 finally:S._render_lock.release()


def frame_counts(parts,fps=30):
 """Quantize absolute boundaries, never round each shot duration independently."""
 quantize=lambda t:math.floor(round(t,6)*fps+.500000001)
 return [max(0,quantize(p['start']+p['duration'])-quantize(p['start'])) for p in parts]
