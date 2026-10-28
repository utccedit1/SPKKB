# ผลตรวจความพร้อมระบบ ช่วยด้วยจ้า 1.5.49

วันที่ตรวจ: 28 ตุลาคม 2026 (Asia/Bangkok) · Task P0.5 / P0.2

**ข้อสรุป: ระบบมีฐานทดสอบที่ดี แต่ยังไม่ควรประกาศพร้อมแจกทั่วไป พบข้อผิดพลาดสำคัญเรื่องไฟล์ไทม์ไลน์ไม่สอดคล้องกันและการส่งงานเสียงซ้ำหลัง timeout รวมถึงปัญหากู้สถานะหน้าจอและ cleanup**

รอบนี้เป็นการตรวจและรายงาน ไม่แก้ซอร์สแอป ไม่เปลี่ยนรุ่น ไม่ติดตั้งทับ ไม่ publish และไม่เขียนโปรเจกต์ CapCut จริง ตัวอย่างยืนยันปัญหาใช้ข้อมูลจำลองในโฟลเดอร์ชั่วคราวและ mock บริการภายนอก

## 1. ขอบเขตและหลักฐาน

- อ่าน ARCHITECTURE.md และ TASK_PHASES.md ครบ ตรวจจุดเชื่อม API/UI, สิทธิ์และ state, งานเบื้องหลัง, AI/Webhook, stock, เสียง, การบันทึก/กู้คืน, updater และ packaging
- สำรวจ Python ใน app/ks พร้อม app_shell.py และ run.py รวม 73 ไฟล์ พบ function definitions 618 รายการ รวม nested functions/methods; ไม่มี syntax error ดู function-inventory.md และ function-inventory.json
- รัน Python regression ทั้งหมด: **393/393 ผ่าน** บน Python 3.14.6 ใช้ receipt ชั่วคราว
- JavaScript regression: **11/12 ชุดผ่าน** อีกชุดเป็นข้อผิดพลาดใน test harness ตาม F06; ไม่ใช่หลักฐานว่าหน้าจอจริงเสีย
- JavaScript ของหน้า editor ที่ประกอบจริง 11 script blocks และส่วนขยาย 3 ไฟล์ผ่าน syntax check; ไม่มี placeholder ที่ยังไม่แทนค่า
- ตรวจ bundle self-test และ codesign ของแอปติดตั้ง 1.5.48 และแพ็ก 1.5.49 ผ่านบนเครื่องนี้: ffmpeg/ffprobe อยู่ใน bundle, CLI 0.30.0 ใช้งานได้, STATE จาก import เดิมกับ ks ใช้ชุดเดียวกัน
- รอบแรก sandbox ห้าม bind localhost และทำให้ macOS self-test หยุดที่ XPC; รันทดสอบที่เกี่ยวข้องนอก sandbox แล้วผ่าน จึงไม่จัดสองเหตุการณ์นี้เป็นบั๊กแอป
- ไม่ได้วัด branch/line coverage และไม่ได้เปิดใช้งานทุกฟังก์ชันกับบริการจริง การมีรายชื่อครบหรือ tests ผ่านไม่ได้แปลว่าผ่าน acceptance ทุกเส้นทาง

## 2. ข้อผิดพลาดและสิ่งที่ต้องแก้ เรียงตามความสำคัญ

### F01 — P1: การบันทึกซับและตัด Event อัปเดตไฟล์ไทม์ไลน์สำเนาไม่ครบ

**ยืนยันด้วย fixture:** ฟังก์ชัน apply_guard.commit เขียน draft_info.json ของ timeline และ project root แต่ draft_content.json, draft_info.json.bak และ template-2.tmp ที่มีอยู่ยังเป็นข้อมูลเดิม ตัวอย่างแก้ซับได้ไฟล์ใหม่เพียง 2 จาก 8 ไฟล์ในชุดจำลอง

เส้นทาง event_timeline.apply เมื่อตัด 4 วินาทีเหลือ 2 วินาที ยังทิ้ง root/draft_content.json และ template-2.tmp ทั้งสองตำแหน่งไว้ที่ 4 วินาที เส้นทาง caption_resegment และ proofread มีรายการ mirror แบบเก่าที่ควรตรวจแก้พร้อมกัน

**ผลกระทบ:** ไฟล์ที่แทนไทม์ไลน์เดียวกันไม่ตรงกัน มีความเสี่ยงที่ CapCut โหลดข้อมูลเก่า หรือผลแก้ไม่คงอยู่ตามไฟล์ที่ CapCut เลือกอ่าน การไม่สอดคล้องยืนยันแล้ว แต่ยังไม่ได้ทดสอบว่า CapCut รุ่นใดเลือกไฟล์ใดเมื่อเกิดความขัดแย้ง

**ตำแหน่ง:** app/ks/apply_guard.py:63, app/ks/event_timeline.py:239, app/ks/caption_resegment.py:249, app/ks/proofread.py:163 เทียบเส้นทาง CLI ซึ่งจัดการ mirror ครบกว่าใน app/ks/cli_lab_commit.py

**ควรแก้:** ใช้ตัวสร้างรายการ mirror ร่วมกัน ตรวจ identity ของ active timeline ก่อนเขียน รักษา backup/journal/rollback และแยกไฟล์ pristine backup ออกจาก mirror ที่ต้องอัปเดต เพิ่ม regression ทั้ง project root + Timelines + draft_content + template จากนั้นเปิดตรวจและ export ใน CapCut

หลักฐาน: probe.py, probe-results.json → caption_mirrors / event_cut_mirrors

### F02 — P1: Webhook งานเสียงโหมด auto ส่ง POST ซ้ำหลัง timeout

**ยืนยันด้วย mock:** ตั้ง urlopen ให้ timeout และ max_retries=1 แต่ call_webhook(..., audio_b64=..., send_mode='auto') ยังเรียก 2 ครั้ง: JSON แล้ว multipart

**สาเหตุ:** wrapper โหมด auto จับ Exception รวม timeout/ack แล้วส่งรูปแบบที่สอง แม้ชั้นภายในแจ้งว่าจะไม่ส่งซ้ำ audio_webhook_mode มีค่าเริ่มต้น auto และมีให้เลือกในหน้าจอจริง

**ผลกระทบ:** บริการอาจรับงานแรกไปแล้ว จึงประมวลผล/คิดค่าใช้จ่ายซ้ำ และผู้ใช้ต้องรอนานขึ้น ปัญหานี้อยู่ในเส้นทางเสียง ไม่ใช่ข้อยืนยันว่า CLI planning ปกติส่งซ้ำ

**ตำแหน่ง:** app/ks/ce_ai.py:233–245, app/ks/ce_config.py:208, app/ks/editor_page.html:560

**ควรแก้:** ไม่ fallback เมื่อผลการส่งไม่แน่นอน เช่น read timeout/ack; แยกข้อผิดพลาดที่ชัดเจนว่ารูปแบบไม่รองรับ และให้เลือกส่งใหม่อย่างชัดเจนหากจำเป็น เพิ่ม regression ที่ทดสอบ wrapper auto ไม่ใช่เฉพาะชั้น HTTP

หลักฐาน: probe-results.json → audio_timeout.post_count = 2; ไม่มีการส่งเสียงหรือ prompt จริง

### F03 — P2: งาน CLI ที่หายทำให้หน้าจอค้างและเริ่มงานใหม่ไม่ได้

**ยืนยันด้วย UI harness:** backend หางานไม่พบแล้วตอบ HTTP 200 พร้อม ok:false แต่ UI ล้างรหัสงานเฉพาะ HTTP 400/404 กรณีนี้จึงถูกตีความเป็นการเชื่อมต่อขัดข้อง เก็บรหัสงานไว้และให้กดตรวจงานเดิมซ้ำ การกดวางแผนใหม่ไม่ได้ส่ง start request เลย

**ตำแหน่ง:** app/ks/cli_lab.py:143–147, app/ks/server.py เส้นทาง /api/cli_lab, app/ks/cli_lab_ui.py:93,134,186

**ควรแก้:** ส่งรหัสข้อผิดพลาด job_not_found/project_mismatch ที่ชัดเจนและให้ UI ยุติการติดตามเฉพาะกรณีถาวร รักษางานไว้เมื่อ offline/401 ชั่วคราว ทดสอบ response จริงของ server เพราะ test เดิมจำลองเฉพาะ 404

หลักฐาน: missing-job-probe.js / missing-job-probe.json → saved_job_retained:true, new_job_requests:0

### F04 — P2: ผลที่สร้างเสร็จยังไม่คืนหน้าจอหลังปิด/เปิดใหม่

**ยืนยันจากการตามเส้นทางโค้ด:** watch ล้าง active job เมื่อ state=done ก่อน finish เตรียมนำเข้า; plan/install เก็บในตัวแปรหน้าจอ และโฟลเดอร์ผลอยู่ใน input ไม่มีรายการผลสำเร็จตาม owner/project ให้หน้าใหม่ค้นกลับมา แม้ backend จะ persist receipt แล้ว

**ผลกระทบ:** ไฟล์ผลยังอยู่ แต่ผู้ใช้ต้องจำโฟลเดอร์เพื่อเตรียมนำเข้าใหม่ หรือเข้าใจผิดว่าต้องตัดใหม่ เป็นงานค้าง P2.1b ที่ยังพบในซอร์สปัจจุบัน ไม่ใช่ ticket หมดอายุ: ticket รุ่นนี้ไม่มี time expiry แล้ว

**ตำแหน่ง:** app/ks/cli_lab_ui.py:81,120–138,208 และ app/ks/job_store.py ซึ่งมี load ตาม token แต่ไม่มีรายการผลสำเร็จสำหรับ UI

**ควรแก้:** เพิ่มรายการ “ผลล่าสุดที่ยังไม่ใส่โปรเจกต์” ตามเจ้าของและโปรเจกต์ กู้สถานะจาก receipt ฝั่ง server พร้อมเวลา/ที่มาและ hash เดิม ห้าม refresh snapshot แล้ว commit โดยไม่ให้ผู้ใช้ตรวจ

### F05 — P2: cleanup ในแอปไม่ตรงนโยบายเก็บ 5 รุ่น และไม่ครอบคลุมชื่อแพ็กจริง

**ยืนยันด้วย fixture:** มี dist-1.5.44 ถึง dist-1.5.49 แต่ preview เสนอให้ย้าย 4 รุ่น เก็บเพียง 1.5.48–1.5.49 เพราะใช้ versions[:2] แทน 5 รุ่น

นอกจากนี้ pattern รับเฉพาะ dist-X.Y.Z/build-X.Y.Z แต่แพ็กจริงบนเครื่องใช้ dist-X.Y.Z-final ซึ่งไม่เข้ารายการนี้ แม้ build_root จะรู้จัก suffix -final อีกทั้งปลายทางเป็น .cleanup_trash ภายใน workspace ไม่ใช่ macOS Trash

**ตำแหน่ง:** app/ks/storage_manager.py:77–80,92,100

**ควรแก้:** ทำ retention policy เดียวกันระหว่างปุ่มในแอปกับขั้นหลัง release รองรับชื่อแพ็กจริง เก็บ 5 รุ่น ตรวจรุ่นที่ใช้อยู่/สื่ออ้างอิงก่อนย้าย และคงกู้คืนได้ ข้อผิดพลาดอ่าน draft_biz_config.json จากรอบก่อนเป็น guard ที่หยุดเพื่อความปลอดภัย ไม่ควรข้าม guard เพื่อบังคับ cleanup

หลักฐาน: probe-results.json → retention; รายการ bundle ที่พบจริงมี 1.5.44–1.5.49 รวม 6 รุ่น รอบนี้ไม่ได้ย้ายไฟล์ใด

### F06 — P2: test โฟลเดอร์ stock เสีย และยังมี test ผูก path เครื่องพัฒนา

stock_folder_ui_test.js อ่าน raw string ใน cli_lab_ui.py จึงเจอ __RUN_MONITOR_JS__ ก่อน Python แทนค่า เกิด ReferenceError และหยุดก่อนทดสอบพฤติกรรมจริง

**ยืนยันแยกแล้ว:** สำเนา test ใน audits ที่เปลี่ยนเฉพาะการโหลด JS ให้ใช้โมดูลที่ประกอบจริงผ่านทุก assertion เดิม จึงไม่สรุปว่าปุ่มเลือกโฟลเดอร์ในแอปเสีย

cli_lab_ui_recovery_test.js:2 ยังระบุ /opt/homebrew/bin/python3 โดยตรง ทำให้การตรวจบนเครื่องที่ไม่มีตำแหน่งนี้ล้มเหลวได้

**ควรแก้:** โหลด JS ผ่านขั้นประกอบเดียวกับแอป ใช้ interpreter ที่ค้นพบจริงหรือ environment override แล้วนำทั้ง 12 ชุดเข้าเกณฑ์ตรวจ release

หลักฐาน: js-tests.json, stock-folder-composed-probe.js / .txt

## 3. ตารางความพร้อมของแต่ละกลุ่ม

| กลุ่มฟังก์ชัน | ผลตรวจรอบนี้ | ความพร้อม/ข้อจำกัด |
|---|---|---|
| เปิดแอป, runtime, import state | self-test สองรุ่นและ syntax ผ่าน | พร้อมบนเครื่องนี้; ไม่แทน fresh install เครื่องอื่น |
| Login, license, admin, API key แยกผู้ใช้ | auth/security และ owner isolation regression ผ่าน; ตรวจ server/auth/config | ไม่ login หรือแก้บัญชีจริง; ยังไม่ยืนยัน cloud policies ปัจจุบันจาก backend |
| เลือกโปรเจกต์, workspace, active timeline | tests สอง workspace, secondary timeline, source guards ผ่าน | ไม่เปิดหรือเปลี่ยนโปรเจกต์จริง |
| อ่านซับ, เลือกซับ, ไฮไลต์, Super Text, แปล | regression captions/style/highlight ผ่าน | F01 กระทบการบันทึก; ภาพจริง/ฟอนต์/safe area ยังต้อง acceptance |
| แบ่งซับ, คำทับศัพท์, ตรวจคำผิด | regression resegment/loanwords/proofread ผ่าน | ตรวจ mirror ตาม F01; ไม่ส่งซับจริงไป AI |
| AI routes, แชท, B-roll คำค้นอังกฤษ | regression routing, English-only, diagnostics ผ่าน | งานเสียงมี F02; timeout เครื่องอื่นยังไม่มีหลักฐานสาเหตุ |
| CLI วางแผน/ตัด/ตกแต่ง | story/planning/length/CLI tests ผ่าน | F03/F04; ตรวจความหมายและรอยตัดจริงเพิ่ม |
| Event/หลายคลิป/หลายคน | event/review/source constraints ผ่าน | F01; ไม่ยืนยัน speaker identification อัตโนมัติทุกกรณี |
| Multicam/nested/align | regression nested, audio, timing ผ่าน | schema บางชนิดปฏิเสธไว้; ต้องตรวจ draft จริงแต่ละชนิด |
| Artlist/Stock Bridge | bridge/retry/restart/download timeout tests ผ่าน | เป็นเว็บ automation; รอบนี้ไม่ค้น/ดาวน์โหลดหรือทดสอบบัญชีจริง |
| โฟลเดอร์สื่อ/cache/ไม่ซ้ำ/PiP | project storage/composition/cache tests ผ่าน; folder UI แบบประกอบจริงผ่าน | PiP ยังเป็น opt-in; acceptance stock บนเครื่องอื่นยังค้าง |
| เสียงพูด/เพลง/fade/ต่อเพลง | audio-level/music/media-scenario tests ผ่าน | ไม่ได้ฟัง playback หรือ export ใหม่; ค่า peak ไม่ใช่ LUFS |
| ตัดช่วงเงียบ/render/SFX | regression ที่มีผ่าน ตรวจ guard เส้นทางร่วม | ไม่ export งานจริง; ไม่มีหลักฐานว่า codec/input ทุกแบบผ่าน |
| นำเข้า CLI/backup/rollback/history | tests hash/owner/media/receipt/transaction ผ่าน | เส้นทาง CLI ครบกว่าเส้นทางซับ/Event; recovery UI ยังมี F03/F04 |
| Cleanup/undo | restore/reference guards ที่มีผ่าน | F05 และ retention หลัง release ยังไม่รวมเป็นนโยบายเดียว |
| Update/install/distribution | updater regression, bundle signature/self-test ผ่าน | ไม่ติดตั้งทับจริง ไม่ตรวจ public download ใหม่; signing/notarization และ TCC เครื่องอื่นยังค้าง |
| คู่มือ/รายการรองรับ/ซอร์ส repository | ตรวจเทียบแผนและโครงสร้าง | P5.1/P5.2 ยังเปิด; root ไม่ใช่ Git repository ของซอร์ส |

## 4. รุ่นและข้อสังเกตด้านการแจก

- ซอร์ส app/version.json: **1.5.49**
- แพ็ก app/dist-1.5.49-final/ช่วยด้วยจ้า.app: **1.5.49**
- แอปติดตั้งและ process ที่กำลังรัน: **1.5.48** ที่ ~/Applications/ช่วยด้วยจ้า.app
- CapCut กำลังเปิดอยู่ ไม่ได้ปิด/สลับโปรเจกต์/นำผลเข้า
- release_repository/version.json ในเครื่องยังเป็น **1.5.1** เป็น checkout เก่า ไม่ใช่หลักฐานว่ารุ่น public ยังเก่า รอบนี้ไม่ได้ query public manifest
- codesign verify ผ่านยืนยันความสมบูรณ์ของ signature ที่มี ไม่ได้ยืนยัน Developer ID/notarization หรือ Gatekeeper บนเครื่องใหม่
- ยังไม่ได้สำรวจสถานะงานค้างจากหน้าจอแอปหรือ receipt จริงเพื่อหลีกเลี่ยงอ่านเนื้อหางาน ไม่ควรแทนแอปที่เปิดอยู่จากผลตรวจนี้

## 5. ลำดับแก้ที่แนะนำ

1. F01: ทำ mirror transaction ให้ครบทุกเส้นทางเขียน พร้อม regression และ CapCut acceptance
2. F02: หยุดส่งเสียงซ้ำเมื่อ timeout/ack ใน auto mode
3. F03 และ F04: กู้งาน/ผลสำเร็จให้กลับมาทำต่อได้ และหลุดจากสถานะงานที่หายอย่างถูกต้อง
4. F05 และ F06: ทำ cleanup ตรงนโยบาย และซ่อมเกณฑ์ตรวจ UI ให้ครบ
5. จากนั้นตรวจ clip สั้น/5–6 นาที, แนวตั้ง/แนวนอน, muted/detached audio, multicam, export และ fresh install/update บน Mac อีกเครื่อง ก่อนประกาศพร้อมแจกทั่วไป

## 6. ไฟล์หลักฐานรอบนี้

- python-tests.txt: รอบ sandbox มีข้อจำกัด localhost 1 รายการ
- python-tests-unrestricted.txt: 393 tests ผ่าน
- js-tests.json: ผลเดิมครบ 12 ชุด
- syntax-checks.json: Python 73 ไฟล์ และ JS ที่ประกอบจริง
- bundle-checks.json: codesign ผ่าน และ self-test รอบ sandbox ที่ติด XPC
- bundle-self-tests-unrestricted.json: self-test ทั้ง 1.5.48 และ 1.5.49 ผ่าน
- probe.py / probe-results.json: F01, F02, F05 ด้วย fixture
- missing-job-probe.js / .json: F03
- stock-folder-composed-probe.js / .txt: แยกสาเหตุ F06
- function-inventory.md / .json: inventory 618 function definitions สำหรับใช้ตรวจต่อ

ความเสี่ยง/ข้อจำกัดที่ยังไม่พิสูจน์ไม่ถูกนับเป็นบั๊กยืนยัน และรายงานนี้ไม่รับรองว่าใช้งานได้ครบทุกเครื่องหรือทุก CapCut schema
