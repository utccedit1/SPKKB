# Release 1.5.57 — B-roll 0 ภาพ

เผยแพร่ https://github.com/utccedit1/SPKKB/releases/tag/v1.5.57 แล้ว ตัวอัปเดตใช้ main manifest cf4aab08941b69c737b83a981032948a16a73232

แก้แทร็กภาพที่ปิดไว้ถูกนับเป็นภาพทับช่วง; ตรวจภาพเดิมที่ครอบคลุมทั้ง timeline ก่อนเรียก AI/Artlist; เพิ่มเหตุผลและจำนวนข้ามทุกเงื่อนไข แยกจำนวนค้นจริงจากช่วงที่ยังไม่เริ่มค้น; เก็บสรุปงานล้มเหลวและไม่แสดงข้อความหยุดซ้ำ รักษาภาพเดิมที่เปิดอยู่และไม่แก้โปรเจกต์หากไม่มีผลที่ใช้ได้

Python 455 tests + JavaScript 15 suites ผ่าน; bundled self-test, code signature, required modules, ZIP CRC และ credential filename exclusion ผ่าน ดาวน์โหลดสาธารณะครบ 157153679 bytes SHA256 a5803a6a09d90dafc29f6ba5546c338b7c8f6467a51df198eb096a9dba924f4c

ผู้ใช้ยืนยันว่างานเกิดบนเครื่องอื่น ไม่ได้เข้าถึง receipt/โปรเจกต์นั้น จึงยังไม่ยืนยันสาเหตุเฉพาะงานจาก log ท้ายชุด การทดสอบ stock/AI ใช้ค่าจำลอง ไม่ได้ยืนยัน live Artlist batch หรือ CapCut playback/export รอบนี้ ไม่แก้โปรเจกต์จริง ไม่ข้าม retention guard ที่เคยปฏิเสธเพราะอ่าน metadata สื่ออ้างอิงไม่ได้

ติดตั้งผ่าน updater สำเร็จ receipt=installed, Info.plist 1.5.57, installed signature/self-test ผ่าน ไม่ยืนยัน native window หรือ playback รอบนี้ ซอร์สอัปโหลด branch source/readiness-fixes-2026-10-28 commit c55a1133faa568da5920b59d2b654cfbf5df3b21
