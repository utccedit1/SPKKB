"""Persistent, file-bound sound descriptions; audio is sent only on explicit request."""
import base64,hashlib,json,os,subprocess,tempfile,threading,urllib.error
from pathlib import Path
from . import ce_config as Config

_LOCK=threading.RLock()

def _store():return Path(Config.CONFIG_DIR)/'sfx_library.json'
def _read():
 try:
  data=json.loads(_store().read_text());return data if isinstance(data,dict) else {}
 except (OSError,ValueError):return {}
def _file(folder,relative):
 from .ce_features import AUDIO_EXTS
 root=Path(folder).expanduser().resolve();p=(root/relative).resolve()
 if not relative or not p.is_relative_to(root) or not p.is_file() or p.suffix.lower() not in AUDIO_EXTS:raise ValueError('ไม่พบไฟล์เสียงที่เลือกในโฟลเดอร์นี้')
 if p.stat().st_size>32*1024*1024:raise ValueError('ไฟล์เสียงใหญ่เกิน 32 MB')
 return root,p

def _stamp(p):
 st=p.stat();return {'size':st.st_size,'mtime_ns':st.st_mtime_ns}

def entries(folder):
 root=Path(folder).expanduser().resolve();result={}
 with _LOCK:data=_read().get(str(root),{})
 for relative,entry in data.items():
  try:
   _,p=_file(str(root),relative)
   if entry.get('stamp')==_stamp(p) and isinstance(entry.get('description'),str):result[relative]=entry
  except (OSError,ValueError,AttributeError):continue
 return result

def descriptions(folder):return {k:v['description'] for k,v in entries(folder).items()}

def save(folder,relative,description,source='human',provider='',expected=None):
 root,p=_file(folder,relative);description=str(description).strip()[:800]
 if not description:raise ValueError('กรอกลักษณะเสียงก่อนบันทึก')
 stamp=_stamp(p)
 if expected is not None and expected!=stamp:raise ValueError('ไฟล์เสียงเปลี่ยนระหว่างวิเคราะห์ กรุณาลองใหม่')
 with _LOCK:
  data=_read();group=data.setdefault(str(root),{});group[relative]={'description':description,'source':source,'provider':provider,'stamp':stamp}
  dest=_store();dest.parent.mkdir(parents=True,exist_ok=True)
  fd,name=tempfile.mkstemp(dir=dest.parent,prefix='.sfx_')
  try:
   with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False)
   os.replace(name,dest)
  finally:
   if os.path.exists(name):os.unlink(name)
 return {'ok':True,'catalog':descriptions(str(root)),'entries':entries(str(root))}

def provider():
 from . import core_engine as C
 conf=C.load_config()
 if conf.get('audio_backend')=='webhook' and str(conf.get('audio_webhook_url') or '').strip():return 'Webhook งานเสียง'
 if conf.get('audio_api_key') or conf.get('gemini_api_key'):return 'Gemini งานเสียง'
 if conf.get('webhook_audio') and conf.get('webhook_url'):return 'Webhook งานเสียง'
 return ''

def analyze(cfg):
 from . import core_engine as C,event_clip as E
 from .ce_autoclip import ac_ffmpeg_bin
 if cfg.get('send_audio') is not True:raise ValueError('ยืนยันส่งไฟล์เสียงให้ AI งานเสียงก่อน')
 label=provider()
 if not label:raise ValueError('ยังไม่ได้ตั้งค่า AI งานเสียง ไปที่สมอง AI: เลือก Gemini ที่รับเสียง หรือ Webhook งานเสียงที่รับไฟล์ได้ Webhook ข้อความใช้แทนไม่ได้')
 root,p=_file(C.clean_fs_path(cfg.get('dir','')),cfg.get('file',''));stamp=_stamp(p)
 cached=entries(str(root)).get(cfg['file'])
 if cached and cached.get('source')=='audio_ai' and not cfg.get('force'):return {'ok':True,'cached':True,'catalog':descriptions(str(root)),'entries':entries(str(root)),'provider':label,'dir':str(root),'file':cfg['file']}
 E.progress(message='กำลังอ่านไฟล์เสียงจริงและเตรียมตัวอย่างไม่เกิน 12 วินาที')
 command=[ac_ffmpeg_bin(),'-nostdin','-v','error','-i',str(p),'-t','12','-vn','-ac','1','-ar','16000','-f','wav','pipe:1']
 result=subprocess.run(command,capture_output=True,timeout=30)
 if result.returncode or len(result.stdout)<100:raise ValueError('อ่านไฟล์เสียงไม่สำเร็จ กรุณาลองเปิดฟังไฟล์นี้ก่อน')
 if _stamp(p)!=stamp:raise ValueError('ไฟล์เสียงเปลี่ยนระหว่างอ่าน')
 E.progress(message='ส่งตัวอย่างเสียงจริงให้ '+label+' / รอวิเคราะห์ลักษณะเสียง')
 conf=C.load_config()
 prompt='Listen to the attached audio. Describe ONLY what is audible, not filenames. Identify sound character, mood, suitable editing uses and situations to avoid. If audio cannot be accessed return {"error":"audio unavailable"}. Keep the description under 40 words and other fields under 12 words each. Return JSON {"description":"คำอธิบายภาษาไทยสั้นๆ","mood":"...","use":"...","avoid":"..."}. Do not invent speech or sound effects.'
 try:
  raw=C.call_gemini_audio(conf.get('gemini_api_key',''),conf.get('gemini_model','gemini-flash-latest'),prompt,base64.b64encode(result.stdout).decode(),mime='audio/wav',max_tokens=2048,timeout=75,max_retries=1)
 except TimeoutError as exc:raise ValueError(label+' ตอบช้ากว่าเวลาที่กำหนด ยังไม่บันทึกผล กดลองใหม่หรือเปลี่ยนสมองงานเสียง') from exc
 except urllib.error.URLError as exc:raise ValueError('ติดต่อ '+label+' ไม่สำเร็จ ยังไม่บันทึกผล กรุณาตรวจการเชื่อมต่อและโควต้าของสมองงานเสียง') from exc

 data=C.parse_gemini_json(raw)
 if isinstance(data,list) and len(data)==1:data=data[0]
 if not isinstance(data,dict) or not isinstance(data.get('description'),str) or not data['description'].strip() or data.get('error'):raise ValueError(label+' ไม่ส่งผลวิเคราะห์เสียงที่ใช้ได้ ยังไม่บันทึก กดลองใหม่หรือตรวจว่าปลายทางรองรับไฟล์เสียงจริง')
 parts=[data['description'].strip()[:400]]
 for key,label_th in [('mood','อารมณ์'),('use','เหมาะกับ'),('avoid','หลีกเลี่ยง')]:
  if isinstance(data.get(key),str) and data[key].strip():parts.append(label_th+': '+data[key].strip()[:100])
 E.progress(message='กำลังบันทึกผลวิเคราะห์เสียง ใช้ซ้ำได้โดยไม่ส่งใหม่',commit_started=True)
 value=save(str(root),cfg['file'],' · '.join(parts),source='audio_ai',provider=label,expected=stamp)
 value.update(dir=str(root),file=cfg['file'],provider=label,audio_sent=True,excerpt_seconds=12,audio_sha256=hashlib.sha256(result.stdout).hexdigest())
 return value
