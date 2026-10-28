# Release 1.5.51 — B-roll อย่างเดียว

เผยแพร่และติดตั้งบนเครื่องพัฒนาแล้ว วันที่ 28 ตุลาคม 2026

- Release: https://github.com/utccedit1/SPKKB/releases/tag/v1.5.51
- ZIP: 157135838 bytes
- SHA-256: `7c3848fcfb4033b75f22be3596774c7ee3ac71c7ddb9f8a9ea24703040fbe95a`
- Main manifest commit: `68456e82d272db28d97c79f2d148082dbf748a6d`
- Python regression: 415 tests ผ่าน; JavaScript: 13 ชุดผ่าน
- Bundled self-test, runtime, new modules, code signature, credential filename exclusion และ ZIP CRC ผ่าน
- ดาวน์โหลด public asset ตรวจ size/hash ตรงกัน; updater รุ่นก่อนเห็น 1.5.51
- ติดตั้งผ่าน updater เดิม receipt=installed และตรวจ native window/version 1.5.51 พร้อม panel B-roll อย่างเดียวแล้ว

คงเครื่องมือหาไอเดียเดิม เพิ่มเฉพาะภาพใหม่ปิดเสียงผ่านสำเนาและตรวจ invariant ก่อน import; ใช้ backup/mirror transaction/rollback เดิม

ยังไม่ยืนยันผล live Artlist และ playback/export ของโหมดใหม่ใน CapCut หรือ fresh install เครื่องอื่น ผู้ใช้เริ่มงานจริงหลังติดตั้งแล้ว จึงคงแอปและงานไว้ ไม่ปิดหรือเริ่มงานซ้ำ การล้าง build เก่าหยุดตาม guard เพราะอ่าน metadata โปรเจกต์อื่นไม่ได้ ไม่ข้ามการตรวจนี้
