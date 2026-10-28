# P1.4 — เพิ่ม B-roll อย่างเดียว

28 ตุลาคม 2026 · ฐานซอร์ส 1.5.50 หลัง release (ยังไม่แพ็กหรือเผยแพร่ฟีเจอร์นี้)

เพิ่มโหมดในหน้า B-roll เดิม ใช้สมอง broll อ่านซับปัจจุบันและคิดคำค้นอังกฤษ จากนั้น Stock Bridge ค้น/ดาวน์โหลด Artlist ด้วยบัญชีเจ้าของเดิม โหมดคำค้น/ลิงก์/มีมเดิมยังอยู่

หน้าใหม่มีจำนวนภาพสูงสุด 1–30 ช็อต, ปุ่มหาและเตรียม, ยกเลิก/ตรวจงานเดิมต่อ, รายการผลที่สร้างแล้ว และปุ่มใส่เฉพาะ B-roll หลังตรวจผล ไม่เพิ่มขั้นยืนยันบัญชีหรือขอรหัสผ่านใหม่

ขอบเขตการเขียนถูกตรวจด้วย validate_additions: ข้อมูลโปรเจกต์เดิม ความยาว แทร็ก/segment/material เดิมต้องตรงกันทุกฟิลด์ เพิ่มเฉพาะแทร็กภาพใหม่กับวัสดุ companion ที่จำเป็น ปิดเสียงภาพใหม่ ไม่เรียก cut/align/resegment/normalize_speech/style/motion/music/PiP วางภาพใหม่เหนือ main และใต้ text โดยไม่ปรับลำดับของซับเดิม หาก schema ทำไม่ได้จะหยุด

CLI ใช้ draft นำเข้าว่างแยกจากต้นฉบับ สื่อที่เตรียมถูกเก็บในโฟลเดอร์โปรเจกต์แบบ content-addressed ก่อนเผยแพร่ผลเป็นสำเนา ไม่อ้างไฟล์ใน temporary scratch ที่จะหายเมื่อจบงาน

import ticket มี contract=broll_only และตรวจ structural invariant ซ้ำทั้ง preview/commit รวมถึงหลังจัดเก็บ assets ใช้ guard hash/media stamps/active timeline/editor closed/project lock/checkpoint/mirror transaction/rollback เดิม ผลสำเร็จอยู่ใน receipt ตาม owner/project ใช้ต่อหลัง reload ได้

## ผลตรวจ

- Python regression ทั้งระบบ **415/415 ผ่าน**: python-tests.txt
- JavaScript **13/13 ชุดผ่าน**: js-tests.json
- focused Python 9 รายการใช้วิดีโอ/เสียงสังเคราะห์จริงและ capcut-cli จริง แต่จำลอง AI/Artlist: focused-tests.txt
- ยืนยันการเพิ่มและ commit สำเร็จโดยแทร็กเดิมเท่าเดิม; ปฏิเสธการเปลี่ยนรอยตัด/เพลง/ซับ/ความยาว/ลบวัสดุเดิม; ยกเลิก/หาไฟล์ไม่ได้/ต้นฉบับเปลี่ยน/ผลถูกแก้ไม่เขียนโปรเจกต์; ภาพเดิมไม่ถูกแทน; partial write ย้อนคืนต้นฉบับ
- UI harness ตรวจแยกโหมดจากมีม, ไม่เขียนก่อนกดใส่, count validation, job_not_found, offline recovery และ failure guard
- JavaScript ของ editor ที่ประกอบจริงผ่าน syntax check และมีแผงโหมดใหม่เพียงหนึ่งตำแหน่ง: ui-checks.json

## ขอบเขตที่ยังไม่ตรวจ

ยังไม่ได้ส่งซับจริงให้ AI หรือค้น/ดาวน์โหลดด้วยบัญชี Artlist จริง ไม่แก้โปรเจกต์ผู้ใช้ และไม่ได้ตรวจ playback/export ใน CapCut หรือแพ็ก/ติดตั้งโหมดนี้ แอปสาธารณะยังเป็น 1.5.50 เดิม

ดูวิธีใช้ต่อใน app/BROLL_ONLY_GUIDE.md หลังเตรียมแพ็กที่รวมฟีเจอร์แล้ว
