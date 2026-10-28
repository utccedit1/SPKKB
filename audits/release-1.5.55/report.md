# CapCut save roundtrip — 1.5.55

หลังผู้ใช้ปลดล็อก ติดตั้ง 1.5.54 ผ่าน updater ได้จริง ตรวจ native UI เห็น log/repair/folder และปุ่ม folder เปิด Finder ที่ cli_lab_assets ได้จริง

ใช้โปรเจกต์แยกกับไฟล์ภาพจำลองในเครื่อง ผ่าน B-roll build/review/commit จริง เปิด CapCut เห็น main และ B-roll ไม่มี missing-media dialog เห็น B-roll ที่ 00:00:02:01 และเล่นถึงจบ 6 วินาที ไม่ส่งผลเข้าต้นฉบับ ไม่เรียก AI/Artlist จริง

หลัง CapCut save พบ ks_role ถูกลบ แต่ชื่อแทร็กเฉพาะและ volume=0 คงอยู่ จึงแก้ repair_materials ใน 1.5.55 ให้รับ exact app-owned name + video type + ทุก segment ปิดเสียง และยังบล็อก material ที่ใช้ร่วมกับแทร็กอื่น มี regression เพิ่ม

ทดสอบ prepare_repair/commit บนโปรเจกต์ที่ CapCut save จริงแล้วผ่าน ตรวจแทร็กก่อน/หลังเหมือนเดิม และไฟล์/registry ตรงกัน (`roundtrip-repair.json`) การเปิดซ้ำหลังซ่อมยังยืนยันภาพไม่ได้ เพราะตัวควบคุม UI เลือกแผงลอย EditPilot แทนหน้าต่างไทม์ไลน์ ไม่อ้างว่าผ่านรอบเปิดซ้ำจาก JSON

Python 432 tests + JS 13 ชุดผ่าน; bundle self-test/signature/runtime/credential filename exclusion และ ZIP CRC ผ่าน
ZIP 157144209 bytes SHA-256 `8ed291e847bb8f808bd8562fd6ba49b58c35d6edc48f24f7f0db3a2d92f29b6c`
Release: https://github.com/utccedit1/SPKKB/releases/tag/v1.5.55

ยังไม่ทดสอบ batch Artlist จริงบนเครื่องปลายทางหรือ export/การฟังเสียงรอบนี้

เผยแพร่และตรวจ public download/hash สำเร็จ manifest main commit `71553c3ed5ed0658c2b6fc4a64b78c689d90acd5`; กลับหน้าหลัก CapCut ผ่านเมนูที่แสดงจริงแล้ว โปรเจกต์ทดสอบยังเก็บไว้

ติดตั้งผ่าน updater แล้ว receipt=installed ตรวจ native window 1.5.55 และเปิดหน้า B-roll โปรเจกต์เดิมพร้อมใช้งาน CapCut อยู่หน้าหลัก
