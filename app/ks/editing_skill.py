"""Portable app edition of chuaydai-editing; curated and versioned, not executable skills."""
import hashlib
import json

PROFILE={
 'id':'chuaydai-editing/marketing-v3',
 'name':'ช่วยด้วยจ้า · การตลาด',
 'source':'skills/chuaydai-editing/SKILL.md + references/style-library.md',
 'evidence':'Reference draft structure; exact motion imitation has not been visually established.',
 'rules':[
  'เลือกวิธีนำเสนอจากหน้าที่ของคำพูด: คำถาม → เหตุผล → ตัวอย่าง → ข้อสรุป ไม่ใช้ความถี่ลูกเล่นแทนการเล่าเรื่อง',
  'การตลาด: ข้อสงสัย → แย้งด้วยเหตุผล → แยกแนวคิด → บทสรุป',
  'แยกซับคำพูดออกจากข้อความออกแบบ รักษาคำพูดจริงและรอยตัดเดิม',
  'ออกแบบเป็นชุดคำที่สัมพันธ์กัน เปิดตามเสียงทีละหน่วยคำ จัดน้ำหนักตามบทบาท หรือปรับสองบรรทัดให้กว้างเท่ากันตามรูปแบบที่ผู้ใช้เลือก มีช่องว่างพักสายตา',
  'ใช้สองบรรทัดอย่างมีหน้าที่ ไม่ให้น้ำหนักทุกคำเท่ากัน ใช้สี accent เฉพาะคำสำคัญ',
  'ตัวอย่างการประยุกต์: หลักการ (รอง) / ยังใช้ได้ (หลัก); เครื่องมือ (รอง) / เปลี่ยน (หลัก); เข้าใจผู้บริโภค (หลัก) / พฤติกรรม จิตวิทยา (รอง)',
  'ใช้ฟอนต์ สี และ safe area ของงานปัจจุบัน ไม่คัดลอก resource หรือบัญชีจาก reference',
  'ไม่เติมคำพูดใหม่ ไม่เดาเวลาจากจำนวนอักษร ใช้เวลา CapCut หรือ forced alignment ของคำเดิมเท่านั้น',
  'โหมดทั้งคลิปในเครื่องใช้เวลาซับทั้งท่อนและระบุให้ชัด ไม่อ้างเป็น AI หรือเป็นเวลารายคำที่วัดได้',
  'เลือก stack/matched/punch/question/contrast/list จากหน้าที่คำพูด ไม่วนแบบสุ่ม; รายการหรือคำถามไม่เปิดล่วงหน้ากว่าเวลาที่วัดได้',
  'แผนทั้งคลิปปรับรายประโยคได้เฉพาะวลีเดิม บรรทัด คำเน้น แบบ โมชั่น และซ่อน โดยใช้เวลาเดิม; บันทึกก่อนพรีวิวและสร้างสำเนา',
  'ไม่เพิ่มเสียง ภาพ stock หรือ speaker PiP จากการเลือกสไตล์ข้อความ',
 ],
 'forms':['stack','matched','punch','question','contrast','list'],
 'weights':{'support':5.5,'normal':7.0,'hero':10.0},
 'motions':['pop','rise','slide','fade'],
 'tones':['base','accent','secondary'],
}

def profile():
 return json.loads(json.dumps(PROFILE,ensure_ascii=False))
def fingerprint():
 return hashlib.sha256(json.dumps(PROFILE,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
