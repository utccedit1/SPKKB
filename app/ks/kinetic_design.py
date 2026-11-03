"""Closed editorial forms and source-grounded revisions of local caption plans."""
import copy
FORMS={'numeric':'ตัวเลข / เปอร์เซ็นต์','stack':'คำหลัก–คำรอง','matched':'สองบรรทัดเท่ากัน','punch':'คำขยี้','question':'คำถาม / จุดตอบ','contrast':'คู่เปรียบเทียบ','list':'รายการ'}
MOTIONS=('pop','rise','slide','fade')

def revise(plan,edits,sources):
 if plan.get('kind')!='caption_full':raise ValueError('แก้รูปแบบได้เฉพาะแผนทั้งคลิปในเครื่อง')
 if not isinstance(edits,list) or not edits or len(edits)>500:raise ValueError('รายการแก้ไขไม่ถูกต้อง')
 out=copy.deepcopy(plan);lookup={b['cue_id']:b for b in out['blocks']};seen=set()
 for e in edits:
  if not isinstance(e,dict) or set(e)-{'framing','camera_move','composition'}!={'cue_id','form','rows','motion','accent','enabled'}:raise ValueError('แก้ได้เฉพาะรูปแบบ คำ บรรทัด คำเน้น และโมชั่น')
  cid=e['cue_id'];b=lookup.get(cid)
  if not b or cid in seen or cid not in sources:raise ValueError('ไม่พบชุดคำต้นทางหรือรายการซ้ำ')
  seen.add(cid);rows=e['rows'];accent=e['accent']
  if e['form'] not in FORMS or e['motion'] not in MOTIONS or type(e['enabled']) is not bool:raise ValueError('รูปแบบหรือโมชั่นไม่ถูกต้อง')
  if not isinstance(rows,list) or not 1<=len(rows)<=3 or any(not isinstance(r,str) or not r.strip() or len(r)>100 for r in rows):raise ValueError('ใช้วลีสั้น 1–3 บรรทัด')
  if e['form'] not in ('list','numeric') and len(rows)>2:raise ValueError('รูปแบบนี้ใช้ได้สูงสุดสองบรรทัด')
  if type(accent) is not int or not 0<=accent<len(rows):raise ValueError('เลือกบรรทัดเน้นให้ถูกต้อง')
  cursor=0;text=sources[cid]
  for row in rows:
   at=text.find(row.strip(),cursor)
   if at<0:raise ValueError('ข้อความเน้นต้องเลือกจากคำพูดเดิมตามลำดับ ห้ามเพิ่มคำใหม่')
   cursor=at+len(row.strip())
  start=min(u['start'] for u in b['units']);end=max(u['end'] for u in b['units'])
  from .kinetic_scene import FRAMINGS,MOVES,composition
  framing=e.get('framing',b.get('framing','keep'));move=e.get('camera_move',b.get('camera_move','static'))
  if framing not in FRAMINGS or move not in MOVES:raise ValueError('การจัดภาพไม่ถูกต้อง')
  geom=composition(e.get('composition',b.get('composition')))
  b.update(composition=geom,framing=framing,camera_move=move,form=e['form'],enabled=e['enabled'],units=[dict(text=r.strip(),row=i,start=start,end=end,timing='caption',weight='hero' if i==accent else 'support',tone='accent' if i==accent else 'secondary' if e['form']=='contrast' else 'base',motion=e['motion']) for i,r in enumerate(rows)])
 if not any(b.get('enabled',True) for b in out['blocks']):raise ValueError('ต้องเหลือข้อความอย่างน้อยหนึ่งชุด')
 return out


def validate_saved(plan,draft):
 """Rebuild source timing, then reapply only the closed source-grounded edits."""
 from .kinetic_full import plan as full_plan
 from .caption_presets import caption_rows
 baseline=full_plan(draft)
 if len(plan['blocks'])!=len(baseline['blocks']) or {b['cue_id'] for b in plan['blocks']}!={b['cue_id'] for b in baseline['blocks']}:raise ValueError('ชุดคำต้นทางเปลี่ยนแล้ว')
 edits=[]
 for b in plan['blocks']:
  units=b['units'];accent=next((i for i,u in enumerate(units) if u['tone']=='accent'),len(units)-1)
  edits.append(dict(cue_id=b['cue_id'],form=b.get('form','stack'),rows=[u['text'] for u in units],motion=units[-1]['motion'],accent=accent,enabled=b.get('enabled',True),framing=b.get('framing','keep'),camera_move=b.get('camera_move','static'),composition=b.get('composition')))
 # Preserve initial mixed entrances unless a revision explicitly replaced them.
 checked=revise(baseline,edits,{s['id']:t for _,s,m,t in caption_rows(draft)})
 for original,b in zip(plan['blocks'],checked['blocks']):
  if [u['text'] for u in original['units']]!=[u['text'] for u in b['units']]:raise ValueError('ลำดับคำผิด')
  for old,u in zip(original['units'],b['units']):
   if old['motion'] not in MOTIONS:raise ValueError('โมชั่นไม่ถูกต้อง')
   u['motion']=old['motion']
 return checked
