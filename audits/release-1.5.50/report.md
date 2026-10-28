# Release 1.5.50 — F01–F06

เผยแพร่ 28 ตุลาคม 2026 (Asia/Bangkok)

- Release: https://github.com/utccedit1/SPKKB/releases/tag/v1.5.50
- Download: https://github.com/utccedit1/SPKKB/releases/download/v1.5.50/SPKKB.app.zip
- ZIP: 157119800 bytes
- SHA-256: df783b740b438a9a8c5a4e71441d0f46f18f9f1a467c231528d624fd371ad9a2
- Public manifest commit: 8a9c99cef25f7b9a6cc3259403c0a1abb5c0c0d5

รวมงานแก้ F01–F06: mirror transaction ร่วม, หยุด audio auto fallback หลัง timeout/ack, job_not_found ปลดงานค้าง, คืนผลสำเร็จจาก receipt พร้อมตรวจ fingerprint เดิม, retention 5 รุ่นและป้องกันโปรเซสที่กำลังเปิด, ซ่อม UI test harness

ตรวจผ่าน: Python 406/406 และ JavaScript 12/12; bundle self-test, codesign verify, ffmpeg/ffprobe/Node/CLI ฝังในแพ็ก, โมดูล cli_results รวมอยู่ใน archive, ไม่พบชื่อไฟล์ credential ต้องห้าม, ZIP CRC/hash/size และ public download ตรงกัน

ตรวจโค้ด updater โดยจำลองเครื่อง 1.5.49: พบ available=true/latest_version=1.5.50 จากข้อมูลสาธารณะจริง

อัปเดตแอปที่ติดตั้งผ่าน backend updater เดิม ซึ่งใช้ guard งานค้างและ backup/rollback โดยไม่ข้าม guard; receipt state=installed, installed version=1.5.50 และตรวจหน้าต่างแอปจริงเป็น 1.5.50 เปิดโปรเจกต์เดิมและแท็บตัดคลิปด้วย AI ได้

ยังไม่ได้ playback/export ใหม่ใน CapCut หรือ fresh install บนเครื่องอื่น; codesign verify ไม่ยืนยัน Developer ID/notarization แพ็กเก่าหยุดเก็บตาม guard เมื่ออ่าน metadata โปรเจกต์อื่นไม่ได้ ไม่บังคับข้ามการตรวจอ้างอิง และไม่ล้าง Trash

หลักฐานเฉพาะเครื่องอยู่ใน audits/release-1.5.50/ ของ workspace: python-tests.txt, js-tests.json, bundle-check.json, archive-check.json, publish.txt, public-updater-check.json, installed-verification.json และ retention.json ไม่รวมเนื้อหางานผู้ใช้ใน Git
