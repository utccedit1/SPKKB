"""Closed editorial recipes; preserve dialogue and camera cuts, never random layouts."""
import copy
CATALOG=[
 dict(id='original',name='แบบเดิม / ปรับเอง',description='วลีครบตามซับ · ใช้รูปแบบรายประโยคที่เลือกไว้',sample='เพื่อทำ / ภารกิจให้สำเร็จ'),
 dict(id='clean',name='สาระเรียบ',description='พักสายตา · เน้นคำสั้นและตัวเลข · เฟด · คงเฟรม',sample='ความคุ้มค่าเงิน'),
 dict(id='story',name='เล่าเรื่องเป็นจังหวะ',description='คำถาม–คู่เปรียบเทียบ–ข้อสรุป · ลอยขึ้นและเลื่อน · ซูมคำขยี้เร็ว',sample='ดูเหมือนธรรมดา / แต่กลับไม่ธรรมดา'),
 dict(id='impact',name='ขยี้ไว',description='คำใหญ่–ตัวเลข · เด้ง · ซูมเข้าเร็ว 0.30 วิ ค้างแล้วออก',sample='30%   20%   10%'),
]
def catalog():return copy.deepcopy(CATALOG)
def apply(plan,style):
 if style not in {s['id'] for s in CATALOG}:raise ValueError('ไม่พบสไตล์การตัดต่อที่เลือก')
 out=copy.deepcopy(plan);out['editing_style']=style
 if style=='original':return out
 for b in out['blocks']:
  form=b.get('form','stack');units=b['units'];duration=max(u['end'] for u in units)-min(u['start'] for u in units)
  b['enabled']=form in ('punch','numeric') if style=='clean' else form in ('punch','numeric','question','contrast','matched') if style=='story' else duration>=.9
  b['camera_move']='snap_in_out' if b['enabled'] and form=='punch' and style!='clean' else 'static'
  for u in units:u['motion']='fade' if style=='clean' else 'pop' if style=='impact' else 'slide' if form=='contrast' else 'rise'
 if out['blocks'] and not any(b['enabled'] for b in out['blocks']):min(out['blocks'],key=lambda b:sum(len(u['text']) for u in b['units']))['enabled']=True
 return out
