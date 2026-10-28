# B-roll source media placeholder — 1.5.53

ผู้ใช้พบ Errno 2 เมื่อไฟล์เดิมใช้ CapCut draftpath placeholder ขั้น remember ของ B-roll-only เรียก Path.stat โดยตรง ต่างจากเส้นทางตัดคลิปที่ resolve paths ก่อนแล้ว การ normalize output ทั้งหมดจะละเมิดเงื่อนไขคงการตัดต่อเดิม จึงใช้ resolved copy เฉพาะตรวจไฟล์และเก็บ media fingerprints เทียบ source project จริง

- broll_auto preflight ตรวจสื่อก่อน AI/stock
- cli_results.remember และ cli_lab_commit.preview resolve media copy สำหรับ broll_only โดยไม่เขียนทับ saved paths ใน output
- source/output hash, media stamps, add-only invariant, backup/mirror transaction/rollback คงเดิม
- Python 423 tests และ JavaScript 13 ชุดผ่าน รวม regression plain/nested project ตั้งแต่ build-review-commit ที่คง placeholder เดิม, missing media หยุดก่อน AI และ media เปลี่ยนบล็อกทั้ง review/commit
- bundle self-test/signature/runtime, credential filename exclusion และ ZIP CRC ผ่าน
- ZIP 157133139 bytes; SHA-256 `1089cd72d04d5d93ac85ed332664258e10525fdf089da44581fe993420708252`
- Release: https://github.com/utccedit1/SPKKB/releases/tag/v1.5.53

ยังไม่ได้ยืนยันโปรเจกต์บนเครื่องปลายทางหรือ live playback/export ไม่เริ่มค้นหรือเขียนโปรเจกต์จริงซ้ำ การตรวจ UI เครื่องพัฒนาถูกจำกัดเพราะหน้าจอล็อก

เผยแพร่สำเร็จ ตรวจ public download size/hash ตรง manifest main commit `47e8184842425bdfa7b7ba3d955b7e341b0c41ac` เครื่องปลายทางตรวจอัปเดตได้ ยังไม่ติดตั้ง native app รอบนี้เพราะหน้าจอล็อก
