# B-roll batch deadline fix — 1.5.52

งานจริงล้มเหลวเมื่อผ่าน 1801 วินาทีด้วยข้อความงานเกิน 30 นาที ขณะค้น/ดาวน์โหลดต่อเนื่อง พบ stock สำเร็จ 16 งาน, no_match 39 งาน และ download_controls 1 งาน ไฟล์ที่ตรวจแล้วคงอยู่ในคลัง ไม่มีผล batch พร้อมนำเข้าจากรอบที่ล้มเหลว

แก้เฉพาะ broll_only ไม่ใช้ total CLI deadline 30 นาที คงขอบเขต AI 300 วินาที/คำขอ, stock 480 วินาที/งาน และ CLI 120 วินาที/คำสั่ง งานอื่นคง total guard เดิม เมื่อ parent progress ยกเลิก/ล้มเหลว จะปิด stock pending เพื่อไม่รับ late receipt พร้อมแสดงจำนวนภาพที่เตรียมได้ ไม่เปลี่ยนการตัดต่อเดิมหรือข้าม import guards

- Python 420 tests และ JavaScript 13 ชุดผ่าน รวม 5 regression ใหม่: batch เกิน 30 นาทีสำเร็จ, งานอื่นยังมี guard, cancel หลัง 30 นาที, parent stop ปิด stock, stock step timeout ยังทำงาน
- Bundle self-test/signature/runtime และ ZIP CRC/credential filename exclusion ผ่าน
- ZIP size 157136124 bytes; SHA-256 `51eb588ba71d4b5982028b17f4d3d3fbdd6adef1d968a08abd9fe7c8aa46783e`
- Release: https://github.com/utccedit1/SPKKB/releases/tag/v1.5.52

ยังไม่เริ่ม AI/stock batch จริงซ้ำหรือ import เข้า CapCut อัตโนมัติ ผลทดสอบใช้ข้อมูลจำลอง ไม่ยืนยัน live batch 20 ภาพหรือ playback/export จากโหมดนี้แล้ว

Public download/hash ผ่านและ manifest main commit `a51f44828acdac1005ee59e5219ca05ee00f161a`; updater รุ่น 1.5.51 เห็น 1.5.52 ติดตั้งสำเร็จ receipt=installed และเปิดโปรเจกต์เดิมหน้า B-roll ใน native window 1.5.52 แล้ว
