"""Closed editorial recipes; preserve dialogue and camera cuts, never random layouts."""
import copy
CATALOG=[
 dict(id='original',name='แบบเดิม / ปรับเอง',description='วลีครบตามซับ · ใช้รูปแบบรายประโยคที่เลือกไว้',sample='เพื่อทำ / ภารกิจให้สำเร็จ'),
 dict(id='clean',name='สาระเรียบ',description='พักสายตา · เน้นคำสั้นและตัวเลข · เฟด · คงเฟรม',sample='ความคุ้มค่าเงิน'),
 dict(id='story',name='เล่าเรื่องเป็นจังหวะ',description='คำถาม–คู่เปรียบเทียบ–ข้อสรุป · ลอยขึ้นและเลื่อน · ซูมคำขยี้ · ค้างถึงคัทใกล้หรือเข้า–ออกเมื่อคัทไกล',sample='ดูเหมือนธรรมดา / แต่กลับไม่ธรรมดา'),
 dict(id='impact',name='ขยี้ไว',description='คำใหญ่–ตัวเลข · เด้ง · ซูมเข้าเร็ว 0.30 วิ ค้างถึงคัทใกล้ · คัทไกลใช้เข้า–ออก',sample='30%   20%   10%'),
]
def catalog():return copy.deepcopy(CATALOG)
def apply(plan,style):
 if style not in {s['id'] for s in CATALOG}:raise ValueError('ไม่พบสไตล์การตัดต่อที่เลือก')
 out=copy.deepcopy(plan);out['editing_style']=style
 if style=='original':return out
 gap={'clean':10,'story':5,'impact':2.5}[style];candidates=[]
 for index,b in enumerate(out['blocks']):
  form=b.get('form','stack');role=b.get('editorial_role');units=b['units'];start=min(u['start'] for u in units);duration=max(u['end'] for u in units)-start
  score={'numeric':6,'contrast':5,'question':4,'matched':3,'punch':3}.get(form,1)
  if role=='detail':score=1
  elif role in ('result','definition'):score=max(score,4)
  eligible=not b.get('editorial_skip',False) and duration>=.9 and (form in ('punch','numeric') if style=='clean' else score>=3)
  b.update(enabled=False,camera_move='static',editorial_reason='พักภาพและคงซับคำพูด',editorial_score=score)
  for u in units:u['motion']='fade' if style=='clean' else 'pop' if style=='impact' else 'slide' if form=='contrast' else 'rise'
  candidates.append((eligible,score,start,index,''.join(''.join(u['text'].split()) for u in units)))
 chosen=[]
 for eligible,score,start,index,text in sorted(candidates,key=lambda row:(-row[1],row[2])):
  if not eligible:continue
  if any(abs(start-other[2])<gap or (text==other[4] and abs(start-other[2])<30) for other in chosen):
   out['blocks'][index]['editorial_reason']='พักจากคำซ้ำหรือจังหวะเน้นที่ใกล้กัน';continue
  chosen.append((eligible,score,start,index,text))
 available=[row for row in candidates if not out['blocks'][row[3]].get('editorial_skip',False)]
 if available and not chosen:chosen=[max(available,key=lambda row:(row[1],-row[2]))]
 for _,score,start,index,text in chosen:
  b=out['blocks'][index];form=b.get('form','stack');role=b.get('editorial_role')
  emphasis=form in ('punch','numeric','contrast') or role=='result' or (style=='impact' and form=='matched')
  b.update(enabled=True,camera_move='snap_to_cut' if emphasis and style!='clean' else 'static',editorial_reason='เน้น'+{'numeric':'ตัวเลข','contrast':'ความต่าง','question':'คำถาม','definition':'นิยาม','result':'ผลลัพธ์'}.get(role or form,'ใจความหลัก'))
 return out
