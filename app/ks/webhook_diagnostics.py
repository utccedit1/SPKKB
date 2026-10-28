"""Local, bounded, owner-scoped transport metadata. Never stores request contents."""
import hashlib,threading,time,uuid
from collections import OrderedDict
_records=OrderedDict();_lock=threading.Lock()
def endpoint_id(url):return hashlib.sha256(str(url).encode()).hexdigest()[:12] if url else ''
def begin(owner,url,feature,input_chars,payload_bytes,max_tokens,timeout):
 token=uuid.uuid4().hex[:12]
 row=dict(id=token,owner=owner,endpoint=endpoint_id(url),feature=feature or 'webhook',input_chars=input_chars,payload_bytes=payload_bytes,max_tokens=max_tokens,timeout=timeout,state='waiting_headers',phase='waiting_headers',elapsed=0,created=time.time(),started=time.monotonic())
 with _lock:
  _records[token]=row
  while len(_records)>100:_records.popitem(last=False)
 return token
def update(token,state,http_status=None):
 with _lock:
  row=_records.get(token)
  if row is None:return
  row.update(state=state,elapsed=round(time.monotonic()-row['started'],2))
  if http_status is not None:row['http_status']=http_status
  if state in ('waiting_headers','reading_body'):row['phase']=state

def recent(owner):
 with _lock:
  rows=[]
  for r in _records.values():
   if r['owner']!=owner:continue
   row={k:v for k,v in r.items() if k not in ('owner','started')}
   if row['state'] in ('waiting_headers','reading_body'):row['elapsed']=round(time.monotonic()-r['started'],2)
   rows.append(row)
  return rows[-10:]

def report(owner):
 from . import core_engine as CE,event_clip as E
 with CE.ai_feature('chatbot'):chat=CE.load_config()
 with CE.ai_feature('broll'):broll=CE.load_config()
 try:cut,_=E.provider_config('utcc')
 except ValueError:cut={}
 def route(cfg):return dict(backend=cfg.get('ai_backend','gemini'),endpoint=endpoint_id(cfg.get('webhook_url')) if cfg.get('ai_backend')=='webhook' else '')
 routes={'chat':route(chat),'broll':route(broll),'cut':dict(backend='webhook_utcc',endpoint=endpoint_id(cut.get('webhook_url')))}
 rows=recent(owner);names={'chat':'แชท','broll':'B-roll ปกติ','cut':'ตัด AI'};lines=['รายงาน AI · เฉพาะการเชื่อมต่อ ไม่เก็บซับ ข้อความแชท รหัส หรือ URL เต็ม']
 for key,r in routes.items():lines.append(names[key]+': '+r['backend']+(' · ปลายทาง #'+r['endpoint'] if r['endpoint'] else ''))
 if routes['chat']['endpoint'] and routes['chat']['endpoint']==routes['cut']['endpoint']:lines.append('แชทและตัด AI ใช้ Webhook เดียวกัน')
 else:lines.append('แชทและตัด AI ใช้คนละเส้นทาง จึงยังใช้ผลแชทยืนยันงานตัดไม่ได้')
 phases={'waiting_headers':'รอส่วนหัว HTTP จากเซิร์ฟเวอร์','reading_body':'ได้รับ HTTP แล้ว รอเนื้อหาคำตอบ','ok':'ได้รับคำตอบครบ','timeout':'หมดเวลารอ','http_error':'เซิร์ฟเวอร์ตอบ HTTP ผิดพลาด','network_error':'เชื่อมต่อขัดข้อง','ack':'ปลายทางรับงาน แต่ยังไม่คืนคำตอบ AI'}
 if not rows:lines.append('ยังไม่มีบันทึก Webhook ในการเปิดแอปรอบนี้ ให้ลองงานที่มีปัญหาแล้วตรวจรายงานก่อนปิดแอป')
 for r in rows:
  lines.append(f"#{r['id']} · {r['feature']} · {phases.get(r['state'],r['state'])} · {r['elapsed']} วินาที / รอได้ {r['timeout']} · ข้อมูล {r['input_chars']} ตัวอักษร ({r['payload_bytes']} ไบต์) · คำตอบสูงสุด {r['max_tokens']} tokens"+(' · HTTP '+str(r['http_status']) if 'http_status' in r else '')+(' · ขั้นล่าสุด: '+phases[r['phase']] if r.get('phase') else ''))
 return dict(ok=True,routes=routes,requests=rows,output='\n'.join(lines))
