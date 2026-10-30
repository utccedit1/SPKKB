# แผนงาน Phase และ Sub Phase — ช่วยด้วยจ้า

อัปเดต: 28 ตุลาคม 2026 · ฐานรุ่น 1.5.56 · อ่าน `ARCHITECTURE.md` ก่อนใช้แผนนี้

สถานะ: `DONE` = ทำเสร็จพร้อมหลักฐานที่ระบุ, `PARTIAL` = มีโค้ดแต่ยังตรวจไม่ครบ, `OPEN` = งานที่จะทำ, `BLOCKED` = ขาดสิ่งจำเป็นที่ระบุ ไม่ใช้คำว่า DONE แทน “น่าจะใช้ได้”

เอกสารนี้เป็น backlog สำหรับรับช่วงต่อ **ไม่ใช่คำสั่งให้ทำทุก Phase หรือเผยแพร่เอง** เลือกขอบเขตตามคำขอผู้ใช้ แล้วระบุ task ID ที่รับทำ ก่อนเริ่มอ่านหลักฐานล่าสุดและตรวจว่าไฟล์/รุ่นที่ติดตั้งตรงกับซอร์สหรือไม่

## ลำดับเริ่มงานแนะนำ

1. ตรวจ P0.2 แล้วแก้ปัญหาที่ผู้ใช้แจ้งล่าสุดก่อน
2. P1.1 เก็บหลักฐาน timeout จากเครื่องที่พบปัญหา; P2.1 ทำ recovery ผลตัดให้จบทั้ง UI และ backend
3. P1.2/P3 ตรวจการใช้งานจริงและคุณภาพงานตัด
4. P4/P5 ก่อนแจกทั่วไป; P6 เป็นทางเลือกที่ต้องตกลงขอบเขต

## Phase 0 — ฐานส่งต่องานและการจัดซอร์ส

| ID | สถานะ | งาน / ผลส่งมอบ | เกณฑ์จบ |
|---|---|---|---|
| P0.1 | DONE | โครงสร้าง, แผนงาน, คำสั่งเอเจนต์ที่ root | มี `ARCHITECTURE.md`, `TASK_PHASES.md`, `AGENTS.md`, `AGENT.md` และลิงก์/จุดอ้างอิงตรงกับไฟล์จริง |
| P0.2 | OPEN | สำรวจเครื่องที่จะทำต่อ: source version, installed version, งานค้าง, dependency | บันทึกข้อมูลที่ไม่ลับ แยกเวอร์ชันซอร์สกับแอปจริง และไม่ปิดงานค้าง |
| P0.3 | OPEN | จัดที่เก็บซอร์สจริงและขอบเขต private/public | root ยังไม่มี Git ซอร์ส; `release_repository` มีเพียง manifest ต้องตกลง repository ก่อน init/push; exclude credentials, runtime builds, outputs และสื่อ |
| P0.4 | PARTIAL | รักษาเพียง 5 เวอร์ชันล่าสุด | cleanup วันที่ 28 ต.ค. มี receipt แล้ว; ยังต้องออกแบบ retention หลัง release ที่ตรวจสื่ออ้างอิง/รุ่นที่รันอยู่ ไม่ล้าง Trash เอง |
| P0.5 | DONE (audit) | ตรวจความพร้อมภาพรวมซอร์ส 1.5.49 และรายงานข้อผิดพลาด | `audits/full-readiness-1.5.49/report.md`; 393 Python tests ผ่าน, JS 11/12 (อีกชุด test harness เสีย), ยืนยัน F01–F06; DONE เฉพาะการตรวจ ไม่ใช่งานแก้หรือ acceptance ทุกเครื่อง |

| P0.7 | DONE (audit) | ตรวจความพร้อมหลัง 1.5.55 รวมฟังก์ชันอื่น | `audits/full-readiness-1.5.55/report.md`; 432 Python + 13 JS ผ่าน แต่พบ F01–F07 ด้วย probes เพิ่มเติม; ยังไม่แก้หรือรับรองใช้งานครบทุกเครื่อง |

งานแก้จาก audit: **P0.6 PARTIAL (เผยแพร่ 1.5.50 แล้ว; ยังไม่ CapCut playback/export acceptance)** — แก้ F01–F06 ตาม `audits/readiness-fixes-1.5.49/report.md`; ไม่ใช่การอนุมัติ publish หรือติดตั้งทับแอปที่กำลังรัน

## Phase 1 — เครือข่าย AI และคลังสื่อเสถียร

### P1.1 วินิจฉัย timeout ของเครื่องอื่น — OPEN / เร่งด่วน

- ใช้ 1.5.47 ขึ้นไป ลอง “วางแผนตัดคลิป” ที่เคยล้มเหลว เก็บรายงาน AI/Webhook ก่อนปิดแอป พร้อมเวลาและความยาวต้นฉบับ/เป้าหมาย โดยไม่ส่ง credential หรือซับเต็มเข้าบันทึก
- เทียบ endpoint fingerprint, input/payload size, HTTP status, timeout และ phase ที่หยุดกับแชท อย่าสรุปว่า server ปกติเพียงเพราะแชทตอบ
- ถ้าเข้าถึง Execution Monitor ของ UTCC ได้ ให้อ่านเวลา/สถานะของงานนั้น แยก queue, model, HTTP headers/body และ validation repair ห้ามเปลี่ยน workflow/model โดยเดา
- พิจารณาลด payload alias ซ้ำ/แบ่งงานหนัก เฉพาะหลังตรวจสัญญา Webhook จริง; ต้องไม่ทำให้ flow ที่ใช้อยู่รับ input ไม่ได้
- เกณฑ์จบ: มีหลักฐานเครื่องที่เคยเสีย ระบุสาเหตุหรือขอบเขตที่ยังพิสูจน์ไม่ได้ และทดสอบคำขอเดิมหลังแก้สำเร็จ; ไม่แก้ด้วยการยืด timeout อย่างเดียว

### P1.2 Artlist ดาวน์โหลดครบวงจร — PARTIAL

- เส้นทาง: pair → login → search → select → download → file detected → verify → copy to project → timeline มีภาพ/เสียง
- เก็บความคืบหน้าและเวลารายขั้น แยก no match, เว็บไซต์ไม่พร้อม, สิทธิ์บัญชี, permission โฟลเดอร์, โหลดไม่ครบ และตรวจไฟล์ไม่ผ่าน
- ทดลองทั้ง cache hit/miss, ไฟล์ซ้ำ, สื่อทางเลือก, เพลงโหลดไม่ได้, ยกเลิก และเปิดแอปใหม่หลังล้มเหลว
- เกณฑ์จบ: ใช้งานบนเครื่องผู้ใช้อื่นได้ มีหลักฐานสื่อจริงและเปิดตรวจใน CapCut; งานที่สื่อบางรายการไม่สำเร็จยังแจ้งทางไปต่อและไม่ทำผลตัดทั้งหมดหาย

### P1.3 B-roll ปกติคำค้นอังกฤษ — DONE เฉพาะขอบเขต 1.5.47

ไม่ใช้ซับไทยเป็น fallback เมื่อ AI ล้มเหลว ตรวจ query/keywords และรับ alternative อังกฤษได้ ทดสอบจริงได้ 23 รายการ หลักฐาน `audits/ai-diagnostics-1.5.47/` หากแก้ส่วนนี้ต้องรักษา regression cases เดิม; ไม่ตีความว่าระบบ stock อื่นเสร็จทั้งหมด

### P1.4 เพิ่ม B-roll อย่างเดียวผ่าน Artlist — PARTIAL (เผยแพร่ 1.5.51 สำหรับทดลองใช้จริง)

- เพิ่มโหมดในหน้า B-roll เดิม โดยคงค้นคำ/ลิงก์และมีมเดิมไว้ ใช้ซับปัจจุบัน ไม่ถอดเสียงใหม่
- เพิ่มได้เฉพาะแทร็กภาพใหม่ปิดเสียงและวัสดุ companion; ตรวจ structural invariant ทั้งก่อนสร้างผลและตอนนำเข้า ห้ามเปลี่ยนรอยตัด ซับ เพลง เสียง โมชั่น ความยาว/ค่าของโปรเจกต์เดิม
- ใช้ผลสำเนา receipts กู้คืน hash/media stamps และ guard/backup/mirror/rollback เดิม ต้องตรวจผลแล้วกดใส่หลังกลับหน้าหลัก CapCut
- หลักฐาน `audits/broll-only-1.5.50/` และ `audits/release-1.5.51/`; เผยแพร่และติดตั้ง 1.5.51 แล้ว ยังรอ live Artlist/CapCut playback acceptance
- เกณฑ์ที่ยังค้าง: ทดสอบค้น/ดาวน์โหลดจริงด้วยบัญชีและข้อมูลที่อนุญาต ตรวจ playback/export ใน CapCut และแพ็กฟีเจอร์ก่อนประกาศว่าใช้ได้ในแอปแจก

## Phase 2 — ผลตัดไม่หายและนำเข้าเข้าใจง่าย

| ID | สถานะ | งาน | เกณฑ์จบ / จุดแก้ |
|---|---|---|---|
| P2.1a | DONE | ยกเลิก ticket นำเข้าอายุ 10 นาที และ persist receipt | 1.5.48; tests หลังรอนาน/โหลด receipt ใหม่/ผิดโปรเจกต์/สื่อเปลี่ยน; `cli_lab_commit.py`, `job_store.py` |
| P2.1b | PARTIAL (ซอร์ส P0.6) | คืน “ผลล่าสุดที่ยังไม่ใส่โปรเจกต์” หลังปิดแอป/เปลี่ยนหน้า | ผู้ใช้ไม่ต้องจำโฟลเดอร์หรือสร้างใหม่; ผูก owner/project, แสดงเวลาสร้างและที่มา; ใช้ hash เดิมตรวจความเปลี่ยนแปลง ไม่ refresh snapshot แล้ว commit เงียบ ๆ |
| P2.2 | PARTIAL (ข้อความ UI P0.6) | แยกอายุแผนที่ยังไม่สร้างออกจากผลที่สร้างแล้วใน UI | อธิบาย plan 1 ชั่วโมงแยกจาก import ticket ไม่มี time expiry; หากแผนเก่าหรือต้นทางเปลี่ยน ชี้ว่าต้องวางแผนใหม่หรือแค่ตรวจนำเข้าใหม่ |
| P2.3 | PARTIAL | UX หลักเหลือขั้นตอนชัดเจน | สถานะวางแผน/ปรับแผน/โหลดสื่อ/สร้าง/รอนำเข้า/สำเร็จ แยกกัน; ใช้ progress ตามงานจริง ไม่แสดงเปอร์เซ็นต์ที่เดา; ไม่มีปุ่มเก่ากดวนแล้ว error เดิม |
| P2.4 | OPEN | ตรวจ interruption และ rollback ของงานหลายเส้นทาง | offline, session หมดอายุ, restart, disk full, source เปลี่ยน, เลือก workspace อื่น, editor ยังเปิด; ไม่ส่งผลข้ามโปรเจกต์ ไม่เขียนค้างครึ่งเดียว |

## Phase 3 — คุณภาพงานตัดที่พร้อมลงโซเชียล

### P3.1 ซับและแบรนด์ — PARTIAL

ใช้ style จากระบบเดิมและ DB Heavent Blk, สีคณะ, safe area, ความอ่านง่าย และ fallback ฟอนต์ที่ชัดเจน ตรวจแนวตั้ง/แนวนอน ชื่อไทย-อังกฤษและซับยาว ฟังตรวจเวลาจริง ไม่ใช่แค่ assert จำนวน segment หากต้องแบ่งเวลาโดยประมาณต้องมีคำเตือน

### P3.2 จังหวะตัดและ keyframe — PARTIAL

ตรวจ cinematic zoom ต่อเนื่อง รอยตัดผู้พูดเดิม ครอปให้เต็มเฟรม ไม่ซูมค้าง/รีเซ็ตโดยไม่ตั้งใจ ลด keyframe ไม่ให้รก ไม่ตัดกลางคำหรือคำลังเลที่จับเวลาไม่มั่นใจ เกณฑ์จบ: เปิด playback และส่งออกตัวอย่างตรวจจุดตัดที่ระบุได้ ทั้งโปรเจกต์ธรรมดาและ multicam

### P3.3 B-roll / Super Text / เพลง — PARTIAL

ภาพไม่ซ้ำโดยไร้เหตุผลและครอบรอยตัดที่ต้องซ่อน; Super Text เป็นวลีขยี้ประเด็นครบความ ไม่ห้วนหรือแต่งข้อเท็จจริง; ใช้สไตล์เดียวกับ Studio; เพลงสัมพันธ์เนื้อหา ได้ยินจริง และต่อ/เปลี่ยนเพลงครอบคลุมคลิป มี fade/ระดับเสียงไม่กลบคำพูด ไม่เปิด speaker PiP เป็นค่าเริ่มต้น

เกณฑ์จบ: ทดสอบคลิปสั้นและคลิป 5–6 นาที ตรวจภาพ เสียง จังหวะ และรายงานการใช้สื่อจริง ไม่ตัดสินจากจำนวน B-roll หรือ Super Text อย่างเดียว

### P3.4 คลิปยาว หลายคน และหลายกล้อง — PARTIAL

ทดสอบหลายไฟล์ต่อกัน + Auto Caption, speaker_ranges, nested multicam, muted audio, ความเร็วคลิปและแหล่งเสียงต่างกัน แยกสิ่งรองรับกับ schema ที่ปฏิเสธอย่างชัดเจน อย่าอ้างว่าระบุผู้พูดอัตโนมัติได้ทุกกรณีจากฟังก์ชันกรองช่วงผู้พูดที่ผู้ใช้กำหนด

## Phase 4 — แจกจ่าย ติดตั้ง และอัปเดต

| ID | สถานะ | งาน | เกณฑ์จบ |
|---|---|---|---|
| P4.1 | PARTIAL | fresh install บน Mac ที่ไม่ใช่เครื่องพัฒนา | login/สิทธิ์โฟลเดอร์/เชื่อมบัญชี/ตัด/นำเข้า/เปิดใหม่ได้โดยไม่ต้องใช้ Codex หรือ runtime ภายนอกที่ลืมแพ็ก |
| P4.2 | PARTIAL | อัปเดตแทนตัวเดิมและรักษาข้อมูลผู้ใช้ | installer มีอยู่; ต้องตรวจเครื่องอื่น เส้นทางติดตั้งที่ต่าง งานกำลังรัน archive ผิด checksum, network หลุด, rollback และไม่มีแอปเปิดซ้ำหลายตำแหน่ง |
| P4.3 | OPEN | signing/notarization และความคงที่ของสิทธิ์ macOS | ตรวจทางเลือก Developer ID/บัญชีที่จำเป็นกับเจ้าของก่อน; ทดสอบ update แล้ว TCC ยังใช้งานตามขอบเขตเดิม ไม่ใช้การรีเซ็ตสิทธิ์เป็นวิธีปกติทุกเวอร์ชัน |
| P4.4 | OPEN | Stock Bridge ติดตั้งง่าย | ประเมิน Chrome Web Store / การแจกส่วนขยายที่เหมาะสม; ไม่อ้างว่ามี OAuth หรือ MCP จนมี integration จริง; ทุกคนใช้บัญชี/pairing ของตนเอง |

## Phase 5 — คู่มือและเกณฑ์ปล่อยรุ่น

- **P5.1 OPEN:** ปรับ `app/CLI_LAB_GUIDE.md`, `README_APP.md`, `stock_extension/README.md` ให้ตรงรุ่นจริง ลดคำสั่งแก้โค้ด/ตัวเลขเก่าที่ชวนสับสน และมีคู่มือผู้ใช้แยกจากเอกสารผู้พัฒนา
- **P5.2 OPEN:** ทำตารางรองรับ “ใช้ได้/ทดลอง/ยังไม่รองรับ” สำหรับ OS, CapCut version/schema, stock provider, input media และข้อจำกัด subtitle alignment
- **P5.3 OPEN:** ทำ regression matrix/CI หลังมี source repository; เลือก tests ตามส่วนที่เปลี่ยนและ full suite เมื่อเปลี่ยนเส้นทางร่วม/Release ไม่สร้าง tests ที่ยืนยันเพียงว่าค่าคงที่ตรงกับโค้ด
- **P5.4 PARTIAL:** Release checklist มี pipeline เดิมแล้ว แต่ต้องผูกกับผล acceptance เครื่องอื่น: version เดียวกันทั้ง source/bundle/manifest, no credentials, runtime พร้อม, ZIP/hash/size ถูก, public download ตรง ก่อนประกาศพร้อมแจกทั่วไป

## Phase 6 — ส่วนขยายภายหลัง (ยังไม่รับปากว่ารองรับ)

- **P6.1 OPEN:** Envato ดาวน์โหลดอัตโนมัติ — สำรวจ integration ที่ผู้ให้บริการรองรับ สิทธิ์แผนสมาชิก/ไลเซนส์ และความเสถียร ก่อนเพิ่ม adapter
- **P6.2 OPEN:** Artlist API/MCP — ยืนยันว่ามีช่องทางทางการที่เข้าถึงและใช้กับบัญชีผู้ใช้ได้จริง แล้วเทียบกับ Stock Bridge ไม่เปลี่ยนเพราะได้ยินว่ามี MCP
- **P6.3 OPEN:** สติกเกอร์/illustration/CapCut assets — สำรวจโครงสร้างและสิทธิ์การใช้ ตรวจนำเข้า/ส่งออกก่อนออกแบบ automation

## วิธีอัปเดตและส่งต่องานทุกครั้ง

เมื่อทำ task ให้เพิ่มบันทึกในตารางด้านล่าง ระบุ task ID, รุ่น/ไฟล์ที่แก้, หลักฐานและสิ่งที่ยังไม่ตรวจ อัปเดตสถานะด้านบนเฉพาะขอบเขตที่ผ่านจริง หากเกิด blocker ให้ระบุสิ่งที่ขาดและงานที่ยังทำต่อได้

| วันที่ | Task | ผล / หลักฐาน | ถัดไป |
|---|---|---|---|
| 2026-10-28 | P2.1a | 1.5.48, 390 tests; `audits/import-review-1.5.48/`; Release และ public download ผ่าน | P2.1b; ไม่ได้บังคับติดตั้งทับแอปที่ผู้ใช้กำลังใช้ |
| 2026-10-28 | P0.4 | เก็บ 1.5.44–1.5.48, ย้าย 115 รายการประมาณ 73.4 GiB ไป Trash; receipt ใน `audits/version-cleanup-2026-10-28/` | ออกแบบ retention หลัง release |
| 2026-10-28 | P0.1 | จัดเอกสาร root 4 ไฟล์ ตรวจ path/ลิงก์และจุดอ้างอิงกับซอร์ส | P0.2/P0.3 และงานที่ผู้ใช้สั่งล่าสุด |

| 2026-10-28 | P1.2 / P3.3 | 1.5.49: คำค้นภาพสั้นและ concrete, verified semantic cache และกันภาพซ้ำ, เตือนเมื่อ B-roll เป็นศูนย์; เปลี่ยนเป็นวัดพีกพูด −4 / เพลง −18 dBFS; 393 tests + UI recovery; สำเนาจากโปรเจกต์ปัจจุบันใส่ภาพ 4 ช็อตและ import พร้อม backup; `audits/stock-audio-1.5.49/` | ยังต้องตรวจ playback/export ใน CapCut และทดสอบค้น-ดาวน์โหลดใหม่บนเครื่องอื่น; รอบนี้ใช้ไฟล์สมาชิกที่ตรวจแล้วและตรวจผลค้นหาบนเว็บจริง |

| 2026-10-28 | P0.4 | หลังออก 1.5.49 ตรวจ retention แล้วหยุดโดยไม่ย้าย 1.5.44 เพราะตัวตรวจพบ draft_biz_config.json อ่านเป็น JSON ไม่ได้ในอีกโปรเจกต์; `audits/stock-audio-1.5.49/retention-blocked.json` | ตรวจว่า metadata นี้เป็นไฟล์ว่าง/รูปแบบอื่นอย่างไรโดยไม่ข้ามการตรวจสื่ออ้างอิง; ขณะนี้ยังเก็บ 1.5.44 เพิ่มชั่วคราว |

| 2026-10-28 | P3.3 acceptance ต่อ | ผู้ใช้เปิด CapCut แล้ว ตรวจเห็น B-roll 4 ชิ้นบนไทม์ไลน์และภาพ cashier ขณะ playback; มีแทร็กเพลง/เสียงพูดและมิเตอร์เสียงขยับ ใช้ Space ได้แต่ coordinate actions ยัง noWindowsAvailable; `audits/stock-audio-1.5.49/capcut-playback-check.json` | ยังไม่ได้ export หรืออ่านมิเตอร์ native เป็นตัวเลข/ฟังยืนยัน subjective; ค่า −4/−18 ยังคือค่าที่วัดจากไฟล์ในรอบก่อน |
| 2026-10-28 | P0.5 / P0.2 สำรวจบางส่วน | ตรวจซอร์ส 1.5.49, แอปกำลังรัน 1.5.48; Python 393 ผ่าน, JS 11/12; self-test/signature สอง bundle ผ่าน; รายงาน `audits/full-readiness-1.5.49/report.md` พร้อม fixture ยืนยัน mirror ไม่ครบ, audio auto POST ซ้ำ, missing-job UI ค้าง, recovery ผลสำเร็จไม่ครบ, cleanup ผิดนโยบาย, test harness เสีย; ไม่แก้ซอร์ส/ติดตั้ง/publish/เขียนโปรเจกต์จริง | แก้ F01/F02 ก่อน F03–F06; ยังไม่ตรวจงานค้างจาก UI, live AI/stock, playback/export, fresh install เครื่องอื่น หรือ public download รอบใหม่ |

| 2026-10-28 | P0.6 / F01–F06 | แก้ mirror ร่วม 5 เส้นทางและตรวจซ้ำก่อนเขียน, หยุด audio auto fallback หลัง timeout/ack, job_not_found ปลดงานค้าง, results receipts/UI recovery ตรวจ hash เดิม, retention 5 รุ่น/-final/ตรวจโปรเซส/Trash+undo, ซ่อม UI harness ใช้ runtime จริง; Python 406 tests และ JS 12 ชุดผ่าน; `audits/readiness-fixes-1.5.49/` | ซอร์สยัง version 1.5.49 ไม่ bump/build/install/publish; ต้องตรวจ CapCut playback/export และการติดตั้งจริงก่อนปล่อยรุ่น; ไม่ส่ง AI/stock จริงหรือเขียนโปรเจกต์ผู้ใช้ |

| 2026-10-28 | P0.3 — source branch | ผู้ใช้เลือก SPKKB เดิมและอนุญาตอัปโหลดซอร์สบน branch ใหม่ `source/readiness-fixes-2026-10-28`; อัปโหลด source commit 6657acb บน branch ใหม่สำเร็จ ใช้ checkout แยกใน source_repository พร้อมรายการไฟล์อนุญาตและ .gitignore กันบัญชี/runtime/build/media; root version.json ของ release คงเดิม | ตรวจ branch ได้ที่ https://github.com/utccedit1/SPKKB/tree/source/readiness-fixes-2026-10-28; ยังไม่ publish Release หรือ merge main |

| 2026-10-28 | P4/P5.4 — Release 1.5.50 (กำลังทำ) | ผู้ใช้อนุญาตแพ็ก เผยแพร่รุ่นใหม่ และเปลี่ยนแอปเป็นรุ่นล่าสุด รวม F01–F06; เริ่มตรวจ runtime/tests/source และงานค้างก่อนอัปเดต | self-test/signature/credential exclusion/ZIP/hash/public download/manifest และตรวจรุ่นที่ติดตั้งจริง |

| 2026-10-28 | P4/P5.4 — Release 1.5.50 | แพ็กซอร์ส F01–F06 ด้วย Python 3.14.6; 406 tests + UI 12 ชุด, bundle self-test/signature/credential exclusion ผ่าน; ZIP 157119800 bytes SHA-256 df783b740b438a9a8c5a4e71441d0f46f18f9f1a467c231528d624fd371ad9a2; public download/manifest ผ่าน; updater รุ่น 1.5.49 เห็น 1.5.50; ติดตั้งผ่าน updater และเปิดโปรเจกต์เดิมใน 1.5.50 แล้ว; `audits/release-1.5.50/` | ยังไม่ playback/export ใหม่หรือ fresh install เครื่องอื่น; retention หยุดตาม guard เพราะ metadata อีกโปรเจกต์อ่านไม่ได้ จึงยังไม่ย้ายรุ่นเก่า |

| 2026-10-28 | P1.4 | เพิ่ม broll_auto.py / broll_auto_ui.py และ CLI operation broll_only; คงโหมดหาไอเดียเดิม; validate_additions ตรวจการตัดต่อเดิมเท่าเดิมทุกฟิลด์และปิดเสียงภาพใหม่, contract ใน import ticket, copy/staging + receipts + rollback; Python 415 tests และ JS 13 ชุดผ่าน; `audits/broll-only-1.5.50/` | ยังเป็นซอร์สหลัง 1.5.50 ไม่ publish/ติดตั้ง ไม่ใช้บัญชีจริงหรือแก้โปรเจกต์ผู้ใช้; ต้อง live Artlist/CapCut playback/export ก่อน release |

| 2026-10-28 | P1.4 / P4 / P5.4 — 1.5.51 (กำลังทำ) | ผู้ใช้อนุญาตออกเวอร์ชันใหม่และติดตั้งโหมด B-roll อย่างเดียวให้ลองใช้จริง; ตรวจซอร์ส/แพ็กก่อน Release และใช้ updater เดิมตรวจงานค้าง | tests/bundle/ZIP/hash/public manifest/install/native UI; ยังไม่เริ่มค้นหรือเขียนโปรเจกต์ผู้ใช้ |

| 2026-10-28 | P1.4 / P4 / P5.4 — Release 1.5.51 | Python 415 tests + JS 13 ชุดผ่าน; bundle self-test/signature/credential exclusion/ZIP/public hash/manifest ผ่าน; เผยแพร่และติดตั้งผ่าน updater เดิมแล้ว หน้า B-roll จริงแสดงใน 1.5.51; `audits/release-1.5.51/report.md` | ยังไม่ยืนยัน live Artlist/CapCut playback/export หรือเครื่องอื่น; retention หยุดตาม guard เพราะ metadata โปรเจกต์อื่นอ่านไม่ได้ |

| 2026-10-28 | P1.4 timeout fix — 1.5.52 | พบงานจริงถูกตัดที่ 1801 วินาทีทั้งที่ stock ยังทำงาน; สำเร็จ 16 downloads, no_match 39 และ download_controls 1 ก่อนจบงาน; แยก B-roll batch ออกจาก total CLI deadline โดยคง per-step bounds และปิด stock เมื่อ parent หยุด; เพิ่ม 5 regression | ตรวจ bundle/public/update และไม่เริ่มงานจริงซ้ำอัตโนมัติ |

| 2026-10-28 | P1.4 — 1.5.52 เผยแพร่/ติดตั้ง | 420 tests + JS 13 ชุด, bundle/ZIP/public hash/manifest ผ่าน ติดตั้งผ่าน updater และเปิดโปรเจกต์เดิมหน้า B-roll ใน 1.5.52 แล้ว; `audits/release-1.5.52/` | ผู้ใช้เริ่มใหม่ได้ คลังไฟล์เดิมยังอยู่; ยังไม่รัน batch จริงหรือ import ซ้ำโดยเอเจนต์ |

| 2026-10-28 | P1.4 / P4.4 — Chrome Save dialog | ผู้ใช้ยืนยัน dialog เลือกชื่อ/โฟลเดอร์ ตรวจ worker เส้นทางเว็บและ official Chrome docs: ต้องตรวจ Ask where to save each file ในโปรไฟล์ปลายทาง; `audits/chrome-save-dialog-1.5.52/report.md` | ให้ผู้ใช้เครื่องปลายทางปิดตัวเลือกและทดสอบ; ไม่เปลี่ยน settings เครื่องนี้หรือเผยแพร่รุ่นใหม่ |

| 2026-10-28 | P1.4 — placeholder 1.5.53 | แก้ remember/preview ใช้ resolved copy เพื่อ stat สื่อ B-roll-only โดยคง output paths เดิม; preflight ก่อน AI; regression plain/nested build-review-commit, missing media และ changed media ผ่าน | แพ็ก/ตรวจ public/update; ยังไม่ยืนยันเครื่องปลายทาง |

| 2026-10-28 | P1.4 — 1.5.53 เผยแพร่ | 423 tests + JS 13 ชุด, bundle/signature/ZIP/public download/hash ผ่าน main manifest 47e8184842425bdfa7b7ba3d955b7e341b0c41ac; เครื่องปลายทางกดอัปเดตได้ | เครื่องพัฒนาหน้าจอล็อก ยังไม่ติดตั้งหรือยืนยัน native UI/live project รอบนี้ |

| 2026-10-28 | P1.4 — log / missing media 1.5.54 | เพิ่ม structured counts/log UI, ลด no_match ซ้ำ/หยุด keyword fallback เมื่อ infrastructure ล้มเหลว; copy+hash B-roll เข้าโปรเจกต์และ merge media registry/local_material_id ใน transaction เดิม; native folder action และซ่อม B-roll เดิมผ่าน review/commit contract | full tests/bundle/public release; ยังต้อง live CapCut playback และเครื่องปลายทาง |

| 2026-10-28 | P1.4 — 1.5.54 เผยแพร่ | 431 Python tests + JS 13 ชุด, bundle/signature/credential exclusion/ZIP/public size/hash ผ่าน manifest c0f01fc24d899fd35ad0566e39ad358c0cae2be9; เครื่องอื่นกดอัปเดตได้ | ยังไม่ติดตั้งเครื่องพัฒนาเพราะหน้าจอล็อก และยังไม่ CapCut live playback/export บนเครื่องที่รายงาน |

| 2026-10-28 | P1.4 / P4.2 — native acceptance 1.5.54 | หลังปลดล็อก ติดตั้งผ่าน updater สำเร็จ native version/log container/เปิด Finder ผ่านปุ่มจริง; โปรเจกต์ทดสอบแยกใช้ภาพจำลอง ผ่าน B-roll build-review-commit เปิด CapCut เห็นสื่อทั้งสองและเฟรม B-roll ที่ 00:00:02:01 เล่นครบ/กลับหน้าหลัก ไม่พบ missing dialog; `audits/release-1.5.54/installed-verification.json` | ยังไม่ทดสอบ live Artlist batch/เครื่องปลายทาง/export และไม่ได้ส่งผลทดสอบเข้าโปรเจกต์ผู้ใช้ |

| 2026-10-28 | P1.4 — CapCut roundtrip 1.5.55 | live CapCut เปิดสื่อ 1.5.54 สำเร็จ แต่พบ save ลบ ks_role และคงชื่อแทร็ก/volume=0 จึงเพิ่ม exact-name + muted recognition สำหรับ repair พร้อมห้าม shared material และ regression | ตรวจ full suite/package/release/install และ repair หลัง CapCut save จริงบนโปรเจกต์แยก |

| 2026-10-28 | P1.4 — 1.5.55 release | 432 tests + JS 13 ชุด, bundle/signature/ZIP/public download/hash ผ่าน main manifest 71553c3ed5ed0658c2b6fc4a64b78c689d90acd5; ซ่อมโปรเจกต์หลัง CapCut save ผ่าน tracks/media/registry checks และกลับหน้าหลักแล้ว | ยืนยันติดตั้ง/native window; ยังไม่ live Artlist batch หรือ export |

| 2026-10-28 | P4.2 — 1.5.55 ติดตั้ง | updater receipt=installed, native window 1.5.55 และหน้า B-roll โปรเจกต์เดิมแสดง; `audits/release-1.5.55/installed-verification.json` | เครื่องอื่นอัปเดตได้; ยังไม่ Artlist batch/export บนเครื่องปลายทาง |

| 2026-10-28 | P0.7 / P0.2 สำรวจบางส่วน | ตรวจซอร์ส/แอปติดตั้ง 1.5.55; 432 Python + 13 JS/self-test/signature ผ่าน; ยืนยัน 7 บั๊ก: shared Gemini fallback, generic media registry, legacy mirror restore, resegment missing-job, stock poll delay, silent export, shared proofread lexicon; รายงาน `audits/full-readiness-1.5.55/report.md` | แก้ F01–F03 ก่อน ตามด้วย F04–F07 และ regression/native acceptance; รอบนี้ไม่แก้ซอร์ส/ไม่ release/ไม่เขียนโปรเจกต์จริง; ยังไม่ live Artlist batch/AI/CapCut export/เครื่องปลายทาง |

| 2026-10-29 | P0.8 — แก้ F01–F07 ซอร์ส / PARTIAL acceptance | แก้ owner-filtered Gemini fallback, generic media registry/copy, legacy mirror transaction, scoped resegment recovery, stock queue wake, silent-video export, owner lexicon/cache; Python 438 + JS 14 ผ่าน; `audits/readiness-fixes-1.5.55/report.md` | ยังไม่ native CapCut import/restore/playback/export หรือ live Artlist batch/AI หลังแก้; ยังไม่ bump/build/release/install ซอร์สและแอปแจกฐาน 1.5.55 |

| 2026-10-29 | P0.8 — ตรวจซ้ำ / F08 แก้แล้ว | พบ generic import คัดลอกต้นฉบับซ้ำเมื่อ placeholder/absolute path ต่างกัน แก้ normalize comparison พร้อม regression; เพิ่ม copy-corruption retry/nested audio tests; Python 441 + JS 14 + editor syntax 3 ผ่าน; `audits/readiness-recheck-1.5.55/report.md`; เปิด/บันทึก CapCut fixture แยก สื่อ 3 ไฟล์ resolve+registry ครบ | UI tool จับ floating EditPilot จึงไม่ยืนยัน native preview/playback/audio/export; ยังไม่ live Artlist batch/เครื่องปลายทาง; ไม่ bump/build/publish/install |

| 2026-10-29 | P0.9 — DONE audit / readiness ยังไม่ผ่าน | ตรวจทุกกลุ่มฟีเจอร์ตาม matrix; browser source UI 11 หน้า/55 navigation/80 captions, width 1280/720/480; login/picker/admin/announcements; 441 Python ใน 54 modules + JS 14 + installed self-test/signature ผ่าน; พบ F09 stored HTML/JS ผ่าน announcement type, F10 apostrophe email ทำ admin handlers syntax เสีย, F11 login announcements 401; `audits/all-features-ui-1.5.55/report.md` | ยังไม่แก้ F09–F11/ไม่เปลี่ยน source version/ไม่ release; live AI/Artlist batch/native playback-export/long soak/เครื่องอื่นยังไม่ครบ; source patches P0.8 ยังไม่อยู่ในแอปแจก |

| 2026-10-29 | P0.10 — แก้/แพ็ก 1.5.56 | รวม P0.8 F01–F08 และแก้ F09–F11; announcement schema/atomic save/public bundled endpoint/plain text renderers; admin identity event listeners; unique header IDs; Stock Bridge 0.1.7; Python 447 + JS 15 และ source browser security check ผ่าน | ตรวจ bundle/package/public download/source push/install ก่อนสรุป release; ยังไม่ live AI/Artlist batch/CapCut playback-export ครบทุกเครื่อง |

| 2026-10-29 | P0.10 — DONE release/install 1.5.56 (acceptance ภายนอกยัง PARTIAL) | public download/hash/ZIP/signature/bundle ผ่าน; main manifest a6c6006bf836d5a1c7dd2b1316936aa054c0fb0c; source branch push แล้ว; updater receipt installed/native window+หน้า B-roll 1.5.56 ผ่าน; `audits/release-1.5.56/report.md` | ต้อง Reload Stock Bridge 0.1.7 ใน Chrome; ยังไม่ live Artlist 10 clips/native playback-export/เครื่องปลายทางครบ; retention reference scan ไม่ผ่านจึงไม่ย้ายรุ่นเก่า |

| 2026-10-29 | P0.11 — B-roll 0/18 จากเครื่องอื่น | ไม่ได้เข้าถึง receipt/โปรเจกต์เครื่องปลายทาง; พบ silent skip และ hidden tracks ถูกนับ occupied; แก้แทร็กปิดไม่ขวาง/coverage preflight/skip reason+counts/failed receipt summary/ไม่พิมพ์ error ซ้ำ; regression 18 blocked ideas = 0 searches/18 skips/ต้นฉบับคงเดิม | ทดสอบรวม/แพ็ก 1.5.57; ห้ามสรุปสาเหตุเครื่องปลายทางจาก log ท้ายชุดเพียงอย่างเดียว ยังต้องดูเหตุผลจากรุ่นใหม่บนเครื่องที่พบปัญหา |

| 2026-10-29 | P0.11 — release 1.5.57 / acceptance เครื่องปลายทางยัง PARTIAL | Python 455 + JS 15; bundled self-test/signature/credential filename/ZIP CRC ผ่าน; public download 157153679 bytes/hash ผ่าน; main manifest cf4aab08941b69c737b83a981032948a16a73232; `audits/release-1.5.57/report.md` | สาเหตุเฉพาะงาน 0/18 บนเครื่องอื่นยังไม่ยืนยัน ต้องดูเหตุผลจาก log ใหม่; ไม่ทดสอบ live Artlist batch/CapCut playback-export รอบนี้; ไม่ข้าม retention guard เดิม |

| 2026-10-29 | P0.11 — ติดตั้ง/อัปโหลดซอร์ส 1.5.57 | updater receipt installed, Info.plist 1.5.57 และ installed signature/self-test ผ่าน; source commit c55a1133faa568da5920b59d2b654cfbf5df3b21 | ยังไม่ยืนยัน native playback/export และงานเครื่องอื่น; เครื่องปลายทางอัปเดตแล้วดู log เหตุผลใหม่ |

| 2026-10-30 | P0.12 — ตรวจซ้ำ 1.5.57 | พบ P1 สถานะ receipt ผิดหลังเขียนสำเร็จจาก fixture และ P1 UI timeout นำเข้าอาจแสดงสถานะไม่ชัด; Python 455 ผ่านเมื่ออนุญาตอ่าน process list, B-roll UI suite ผ่าน; `audits/readiness-review-1.5.57/report.md` | ยังไม่แก้/publish; ควรออกแบบสถานะนำเข้าและ recovery ที่ไม่ POST ซ้ำ พร้อม regression/transaction tests; ยังไม่ตรวจ Artlist/CapCut/เครื่องปลายทางจริง |

| 2026-10-30 | P0.13 — แก้สถานะนำเข้าและหน้าติดตาม B-roll ในซอร์ส | นำเข้า B-roll/CLI เป็นงานติดตามได้ ไม่ส่งเขียนซ้ำหลัง timeout; บันทึก fingerprint ทุกไฟล์ก่อน transaction และตรวจ journal ก่อนสรุปผล; receipt failure หลังเขียนแสดงคำเตือนพร้อมผลจริง; recovery รายการผล; แยกกล่อง log/จำนวน/สถานะและสีประกาศสว่าง-มืด; Python 458 และ JS 15 ชุดผ่าน; `audits/p0-13-broll-status/report.md` | ซอร์สหลัง 1.5.57 ยังไม่แพ็ก ติดตั้งหรือเผยแพร่; ยังไม่ live Artlist/CapCut export หรือทดสอบเครื่องปลายทาง; กรณีสถานะไม่แน่ชัดต้องตรวจโปรเจกต์และประวัติก่อนล้างสถานะด้วยตนเอง |

| 2026-10-30 | P0.13 — release 1.5.58 | Python 458 + JS 15, bundle self-test/signature/credential filename exclusion, ZIP CRC/hash และดาวน์โหลดสาธารณะผ่าน; main manifest 41c8e394bd46b6a0346a0cf5467ca2ae5d2c22ed; `audits/release-1.5.58/report.md` | เครื่องนี้ยังเปิด 1.5.57 จึงไม่ปิดแอปทับหน้าจอที่ผู้ใช้เปิดไว้; ยังไม่ทดสอบ Artlist batch หรือ CapCut export บนเครื่องปลายทาง; retention guard เคยหยุดเพราะ metadata โปรเจกต์อื่นอ่านไม่ได้ |
