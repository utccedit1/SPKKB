# ผลแก้ F01–F06 จากการตรวจความพร้อม

28 ตุลาคม 2026 · P0.6 · ซอร์สฐาน 1.5.49 (ยังไม่ออกเวอร์ชันใหม่)

แก้ทั้งหกหัวข้อในซอร์สแล้ว พร้อม regression ที่จับพฤติกรรมเสียจริง สถานะ P0.6 ยัง PARTIAL สำหรับการส่งมอบเป็นแอป เพราะยังไม่แพ็ก/ติดตั้งหรือทดสอบ acceptance ใน CapCut

| ข้อ | การแก้ | หลักฐาน |
|---|---|---|
| F01 | เพิ่ม mirror_updates และ assert_unchanged ใน event_timeline; ใช้กับการสร้างซับ, Event cut, resegment, proofread และ CLI import; ตรวจ ID/โครงสร้าง mirror และเก็บ pristine backup เดิม | regression ใหม่ตรวจไฟล์ root/Timelines ทั้ง draft_info, draft_content, .bak, template-2; จำลองเขียนขาดกลางทางแล้วย้อนทุกไฟล์กลับได้ |
| F02 | audio auto เลือก JSON โดยไม่ fallback เป็น multipart เมื่อ timeout/ack; ยังเลือก multipart โดยตรงได้ | mock timeout/ack ยืนยัน POST ครั้งเดียว |
| F03 | backend ส่ง code=job_not_found เมื่อ receipt หาย/เสียหรือผิด owner/project; UI ยุติติดตามงานถาวรและเปิดให้เริ่มใหม่ ส่วน offline/401 ยังเก็บสถานะ | Python missing/corrupt receipt + UI HTTP 200/ok:false/code ที่ตรง backend |
| F04 | เพิ่ม cli_results.py และ receipts ชนิด results; จด owner/project/source hash/output hash/media stamps ตั้งแต่สร้างเสร็จ; หน้าใหม่ค้นผลย้อนหลังและให้เลือกตรวจ/นำเข้า; adopt ticket รุ่นก่อนโดยเก็บ fingerprint เดิม; imported ไม่แสดงเป็นผลรอนำเข้า | restart/owner/project isolation; เปลี่ยน source/output/media ต้องหยุด; UI เริ่มหน้าว่างแล้วเลือกผลสำเร็จเดิมได้ |
| F05 | เก็บ 5 รุ่นล่าสุดพร้อมรุ่นปัจจุบัน/ที่กำลังรัน รองรับ -final ตรวจโปรเซสทั้ง preview และ move ย้ายเข้า Trash พร้อม manifest/rollback; restore ที่พักไฟล์แบบเก่ายังรองรับ | fixture 7 รุ่น, ปฏิเสธย้ายเมื่อรุ่นเก่าเปิดหลัง preview, move/restore -final, regression reference/restore failure |
| F06 | UI tests โหลด JS หลังประกอบผ่าน Python module; interpreter ใช้ PYTHON environment หรือ python3 ใน PATH | JavaScript ทั้ง 12 ชุดผ่าน |

การคืนผลสร้างเสร็จไม่มี time expiry แต่ไม่ยอมเปลี่ยน hash เดิมเงียบ ๆ ถ้าต้นฉบับ/สื่อเปลี่ยนจะหยุดให้ตรวจ ผู้ใช้ยังมีช่องโหลดโฟลเดอร์ผลเดิมด้วยตนเอง สำหรับผลเก่าที่ไม่มี receipt ที่ใช้งานได้

## ผลทดสอบ

- Python **406/406 ผ่าน** (เพิ่ม regression 13 รายการ): python-tests.txt
- JavaScript **12/12 ชุดผ่าน** รวมกรณีกู้ผลและ job_not_found ใหม่: js-tests.json
- Python syntax ของ app/ks 72 ไฟล์ผ่าน; editor ที่ประกอบจริง 11 script blocks ผ่าน Node syntax check; ไม่มี placeholder เหลือ และมีส่วนแสดงผลล่าสุดเพียงหนึ่งตำแหน่ง: ui-syntax.json
- รอบแรกมีข้อจำกัด sandbox localhost/ps และ fixture สองรายการที่ไม่เคยสร้างไฟล์สื่อ จึงปรับ fixture เป็นไฟล์จำลองและรันชุดเต็มนอก sandbox ภายใต้สิทธิ์ที่ได้รับอนุญาต โดยไม่ลด guard
- tests ของ cleanup ทั้งหมดใช้ Trash จำลองในโฟลเดอร์ชั่วคราว ไม่ย้ายแพ็กจริง

## ไฟล์หลักที่เปลี่ยน

- app/ks/event_timeline.py, apply_guard.py, caption_resegment.py, proofread.py, cli_lab_commit.py
- app/ks/ce_ai.py
- app/ks/cli_lab.py, cli_lab_enhance.py, cli_lab_ui.py, job_store.py, cli_results.py (ใหม่)
- app/ks/storage_manager.py
- app/tests/test_readiness_fixes.py (ใหม่), test_cli_lab_story.py, test_full_app_reliability.py, test_storage_recovery_extra.py, cli_lab_ui_recovery_test.js, stock_folder_ui_test.js
- ARCHITECTURE.md และ TASK_PHASES.md

## ข้อจำกัดและการใช้งานต่อ

1. ยังไม่ได้ build/bump/install/publish จึงยังไม่เปลี่ยนแอปติดตั้งที่ผู้ใช้เปิดอยู่ ผลทดสอบนี้เป็นซอร์สหลังแก้ ไม่ใช่ bundle 1.5.49 เดิม
2. ไม่เขียนโปรเจกต์ CapCut จริง ไม่ส่ง prompt/ซับ/เสียงจริงไป AI และไม่ค้นหรือดาวน์โหลด stock จริง
3. ยังต้องเปิดผลบันทึกด้วย CapCut ตรวจ playback/export โดยเฉพาะ mirror schema และตรวจหน้า recovery ใน native app หลังแพ็ก
4. ยังไม่พิสูจน์ fresh install/TCC/notarization บนเครื่องอื่น และไม่ได้อ้างว่าปัญหา timeout เครื่องอื่นหายจากการแก้ auto retry
5. Cleanup หยุดเมื่ออ่านโปรเซส/การอ้างอิงไม่ได้ และการย้ายข้าม volume ที่ rename ไม่ได้จะ rollback; ไม่ข้าม guard หรือทำสำเนาแล้วลบโดยเงียบ ๆ
6. มี ResourceWarning เดิมในชุดทดสอบ ce_project/HTTPError แต่ไม่มี test failure; ไม่ได้รวมการรื้อโค้ดนอก F01–F06

หลังรันซอร์สหรือแพ็กรุ่นที่รวมการแก้นี้แล้ว เปิดแท็บตัดคลิปด้วย AI จะเห็นผลที่รอนำเข้าของบัญชี/โปรเจกต์นั้น กด “ตรวจและใช้ผลนี้ต่อ” แล้วตรวจรายการก่อนนำเข้า ผลที่สร้างเสร็จไม่ต้องตัดใหม่เพียงเพราะปิดหน้าจอ
