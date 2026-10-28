# B-roll progress, durable media and catalog — 1.5.54

อาการที่ผู้ใช้รายงาน: เตรียม 10 ภาพช้า ไม่เห็นลำดับ/จำนวน ดาวน์โหลดแล้ว CapCut แจ้งสื่อหายและเปิดลิงก์โฟลเดอร์ไม่ได้

ตรวจโค้ดพบว่า UI แสดงเฉพาะ message ล่าสุด แม้ backend มี progress_log; batch ค้นได้สูงสุด 2 เท่าจำนวนเป้าและลองคำสำรองหลายครั้งแม้เป็น download/Chrome error; CLI scratch ไม่มี sidecar จึงได้ local_material_id ว่าง และ commit ไม่ลงทะเบียน draft_materials ทั้งยังพึ่งคลังภายนอกเมื่อไฟล์ไม่ได้อยู่ใน output

แก้:
- log มีเวลา, stage, prepared/downloaded/requested/attempted/skipped และข้อความจริงของ stock bridge รวม byte progress; เก็บสูงสุด 1,000 แถว กู้พร้อม receipt เดิม ไม่มี ETA หรือเปอร์เซ็นต์ปลอม
- กระจาย candidate ทั่วคลิป ข้ามคำค้น no_match ซ้ำใน batch; คงคำสำรองสำหรับ no_match แต่หยุดเมื่อ download/browser error เพื่อไม่รอซ้ำ
- คัดลอกเฉพาะ B-roll ใหม่เข้า cli_lab_assets ภายในโปรเจกต์ ตรวจ hash/stamps ก่อนเขียน ลงทะเบียน draft_materials + local_material_id ทั้ง metadata timeline/root ที่ใช้งาน โดย append และไม่แก้ entries เดิม
- เปิดโฟลเดอร์ผ่าน native opener ที่ project-scoped ไม่ใช้ file://
- ซ่อม B-roll ที่นำเข้าแล้วผ่าน prepare_repair/receipt/review/commit contract ที่ยอมแก้เฉพาะ path/local_material_id ของสื่อในแทร็ก broll_only ไม่เพิ่มช็อต ไม่เรียก AI/stock ไม่เปลี่ยนรอยตัด/ซับ/เพลง/เสียง เมื่อสื่อหายจริงจะหยุด
- ใช้ hash/active-timeline/backup/mirror transaction/rollback เดิม ไม่ข้าม guard

หลักฐาน: Python 431 tests และ JS 13 ชุดผ่าน รวมสื่อหลังลบ output/library, metadata root/timeline, ซ่อมไม่เพิ่มช็อต, รักษา registry เดิม, rollback metadata, infrastructure error ไม่ retry, counts/log และ native-folder request

Bundle self-test/runtime/signature/credential filename exclusion/ZIP CRC ผ่าน ZIP 157142305 bytes SHA-256 `b7402bca79446556c3c4ca8f5846b113ef014fae3bfcd09630f1bb042b6ddf21`
Release: https://github.com/utccedit1/SPKKB/releases/tag/v1.5.54

ข้อจำกัด: Mac หน้าจอล็อก จึงยังไม่ติดตั้งหรือเปิด playback/export ใน CapCut รอบนี้ ไม่ทดสอบ live AI/stock batch บนบัญชีจริงซ้ำ และยังไม่ยืนยันผลบนเครื่องที่ผู้ใช้รายงาน ไม่รับรองเวลารวมของเว็บ Artlist จากการทดสอบจำลอง

เผยแพร่และตรวจ public asset สำเร็จ main manifest commit `c0f01fc24d899fd35ad0566e39ad358c0cae2be9` ยังไม่ได้ติดตั้งตรวจ native UI รอบนี้เพราะเครื่องล็อก
