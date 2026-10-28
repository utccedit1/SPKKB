# ช่วยด้วยจ้า — source branch

ซอร์สรุ่น 1.5.50 พร้อมงานแก้ F01–F06 เผยแพร่เป็น Release วันที่ 28 ตุลาคม 2026 แล้ว

Repository นี้ใช้ main สำหรับ manifest อัปเดตแอป ซอร์สรอบนี้อยู่บน branch `source/readiness-fixes-2026-10-28` โดยไฟล์ version.json ที่ root คงข้อมูล Release เดิม ส่วน app/version.json เป็นเวอร์ชันฐานของซอร์ส

อ่าน ARCHITECTURE.md, TASK_PHASES.md และ AGENTS.md ก่อนแก้ไข ดูผลแก้และข้อจำกัดใน audits/readiness-fixes-1.5.49/report.md

## เตรียมเครื่องพัฒนา

- macOS และ Python ที่รองรับ dependencies ใน app/requirements-app.txt; ใช้ virtual environment แล้วติดตั้งด้วย `python3 -m pip install -r app/requirements-app.txt`
- เตรียม Firebase web configuration ของโครงการและบัญชีที่ได้รับสิทธิ์ผ่านช่องทางส่วนตัวตามกลไกของ app/ks/auth.py ไม่ใส่ไฟล์บัญชีหรือ service account ใน Git
- Runtime ใต้ app/tools ไม่รวมใน Git ต้องเตรียม Node, capcut-cli (ฐานที่ตรวจใช้ 0.30.0), ffmpeg/ffprobe และ media runtime ก่อนทดสอบที่พึ่งพาเครื่องมือเหล่านี้หรือแพ็กแอป ดูรายการที่ app/karaoke_studio_app.spec ต้องการ
- เปิดจากซอร์สด้วย `python3 app/app_shell.py` หลังตั้งค่าที่จำเป็นแล้ว

## ตรวจสอบ

```sh
KS_JOB_STATE_DIR="$(mktemp -d /tmp/chuaydai-tests.XXXXXX)" PYTHONPATH=app python3 -m unittest discover -s app/tests
```

รัน UI tests ใน app/tests/*test.js ด้วย Node runtime ที่เตรียมไว้ ใช้ตัวแปร PYTHON เมื่อ Python ไม่ได้อยู่ใน PATH

ผลบนเครื่องพัฒนา: Python 406/406 และ JavaScript 12/12 ชุดผ่าน Runtime และข้อมูลบัญชีส่วนตัวไม่รวมใน branch นี้ จึงต้องเตรียมบนเครื่องใหม่ก่อนรันทดสอบที่เกี่ยวข้อง Release 1.5.50 ผ่านการอัปเดตจริงบนเครื่องพัฒนาแล้ว ยังต้องตรวจ CapCut playback/export และ fresh install บนเครื่องอื่น
