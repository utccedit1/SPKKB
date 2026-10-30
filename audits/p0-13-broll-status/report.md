# P0.13 — สถานะนำเข้าและ UI B-roll

แก้จาก P0.12 ในซอร์สหลัง 1.5.57 ไม่เปลี่ยนเวอร์ชัน ติดตั้ง หรือเผยแพร่

- `cli_lab_commit.py` บันทึก hash ไฟล์ทั้งหมดที่จะเขียน/ลบลง receipt ก่อน transaction; ตรวจทุกไฟล์และไม่มี transaction journal ก่อนสรุปว่าทำสำเร็จ; รักษา lock, backup, source/output/media checks, mirror และ rollback เดิม หากบันทึกสถานะผลล้มเหลวหลัง transaction แจ้งสำเร็จพร้อมคำเตือน และรายการผลใช้ receipt ตรวจเพื่อกู้สถานะ ไม่ส่งงานเขียนซ้ำ
- `cli_lab.py`, `broll_auto_ui.py`, `cli_lab_ui.py` ทำการนำเข้าเป็น background job ใช้ ticket เดิมเป็น job ID เก็บก่อนส่งคำขอ ติดตาม/คืนสถานะได้ และไม่ retry POST ที่หมดเวลา ปิด cancel ระหว่างนำเข้า หากยังไม่ทราบผลเตือนตรวจโปรเจกต์และประวัติก่อนผู้ใช้ล้างสถานะรอด้วยตนเอง
- UI B-roll แยกกล่องคำแนะนำก่อนนำเข้า สถานะ จำนวนภาพ และบันทึก มีสีปกติ/สำเร็จ/เตือน/ผิดพลาด แยกสีประกาศในหน้า login ด้วย whitelist/textContent เดิม ดูหน้า source ด้วย fixture เฉพาะ localhost ทั้งธีมมืดและสว่าง; fixture ปิด provider และการเขียนงานจริง

Python 458 tests ผ่าน (`python-tests-final.txt`) รวม receipt failure, กันเขียนเมื่อ receipt เริ่มต้นล้มเหลว, guard journal และไม่ replay job หลังโหลด receipt; JavaScript 15 ชุดผ่าน (`js-tests.txt`) รวม offline/resume และการไม่สั่ง commit ซ้ำ การตรวจ UI ใช้ mock/backend จำลอง ไม่ใช่ native acceptance และ fixture เก่ามี error ใน event endpoint ที่ไม่ได้เป็นส่วนของหน้าทดสอบ B-roll

ยังไม่ทดสอบ Artlist batch จริง, CapCut playback/export, เครื่องปลายทาง หรือกรณี crash/power loss จริงทุกจังหวะ หากโปรเจกต์เปลี่ยนหลังนำเข้า fingerprint จะไม่ยืนยันย้อนหลัง ต้องตรวจโปรเจกต์/ประวัติด้วยตนเอง ไม่ได้แก้โปรเจกต์จริง ไม่เผยแพร่รุ่นใหม่
