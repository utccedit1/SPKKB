# Release 1.5.58 — สถานะนำเข้าและ B-roll

เผยแพร่ https://github.com/utccedit1/SPKKB/releases/tag/v1.5.58 และอัปเดต main manifest commit 41c8e394bd46b6a0346a0cf5467ca2ae5d2c22ed

รวม P0.13: กล่อง log และจำนวน B-roll, สีสถานะและประกาศ, นำเข้าติดตามต่อได้เมื่อการเชื่อมต่อสะดุดและไม่ส่งเขียนซ้ำอัตโนมัติ, ตรวจ fingerprint ทุกไฟล์และ transaction journal, แยกคำเตือนเมื่อบันทึกโปรเจกต์สำเร็จแต่บันทึกสถานะล้มเหลว ดูรายละเอียดและข้อจำกัดที่ audits/p0-13-broll-status/report.md

Python 458 tests และ JavaScript 15 ชุดผ่าน; bundled self-test, signature, required modules, credential filename exclusion, ZIP CRC และ public download ผ่าน; 157157072 bytes SHA256 62a11780af9e74ccbc3aaa094d0ca25772f3808e8f96d1f5a8a193363d03644d

แอปเครื่องนี้ยังเปิด 1.5.57 และมีหน้าจอการทำงานอยู่ จึงยังไม่ปิดเพื่อติดตั้งแทน; ผู้ใช้กดอัปเดตเองได้หลังพร้อม ยังไม่ทดสอบ live Artlist batch หรือ CapCut playback/export รอบนี้ และไม่ได้ทดสอบเครื่องปลายทาง ไม่ย้ายรุ่นเก่าข้าม retention guard
