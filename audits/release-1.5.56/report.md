# Release 1.5.56 — 29 ตุลาคม 2026

รวม P0.8 F01–F08: owner-filtered Gemini fallback, generic video/audio/nested media registry + verified copy, timeline mirrors ใน legacy restore/align, resegment missing-job recovery, stock queue wake, silent-video export, owner lexicon/cache และป้องกันคัดลอกต้นฉบับซ้ำเมื่อ path เป็น placeholder

แก้ P0.9 F09–F11: ตรวจ schema/type/ขนาดประกาศก่อน atomic save, plain-text renderers ทุกเส้นทางรวม legacy, ปุ่มแอดมินผูก event listener เพื่อเก็บอีเมล/UID ที่มี quotes ครบ, ประกาศก่อนล็อกอินใช้เฉพาะข้อมูลสาธารณะจาก version.json ในแอป ไม่เปิด local admin records นอกจากนี้ย้าย ID ส่วนหัวเก่าไม่ให้ชนส่วนหัวปัจจุบัน และคง schema/ข้อความหลายบรรทัดของประกาศเดิมเวลาแก้ไข

Stock Bridge 0.1.7: หลังอัปเดตแอปให้กด Reload ส่วนขยายใน Chrome เพื่อใช้ worker ใหม่ ไม่เพิ่มสิทธิ์ส่วนขยาย

## หลักฐาน

- Python 447 tests ผ่าน (`python-tests.txt`), JavaScript 15 suites ผ่าน (`js-tests.json`)
- browser จากซอร์ส: payload ประกาศที่เคย execute marker ไม่รันแล้ว ไม่มี img element ถูกแทรก แสดง literal text, header IDs ไม่ซ้ำ, login เห็นประกาศ bundled public และไม่เห็นประกาศ local/admin (`ui-verification.json`)
- bundle 1.5.56 self-test, code signature, CLI/ffmpeg/ffprobe/runtime/context และ module presence ผ่าน ไม่พบชื่อไฟล์ credential/session ส่วนตัว (`bundle-check.json`)
- ZIP CRC ผ่าน (`archive-check.json`)
- ZIP 157151184 bytes; SHA-256 `f61434cc006ed6cb3c5b7c96b6afeb8e0d4cf15d8f918c7f1e425e209991663f`
- Release: https://github.com/utccedit1/SPKKB/releases/tag/v1.5.56

## ข้อจำกัดจริง

ทดสอบภาพ/เสียงจำลองด้วย ffmpeg ใน regression และเคยตรวจ CapCut save roundtrip แยกใน P0.8 แล้ว แต่รอบนี้ยังไม่ได้ยืนยัน live AI/Artlist batch 10 คลิป, native playback/audio/export หลัง patch และ fresh install/long soak บนเครื่องปลายทาง จึงไม่เรียกว่าไม่มีบั๊กทุกเครื่อง

การ build แรกเผลอเลือก Python 3.9 จาก PATH ในโฟลเดอร์ app จึงไม่ใช้ผลนั้น ชุดที่แจกสร้างใหม่ด้วย Python 3.14.6 ใน workpath แยกและตรวจ bundle self-test/modules/signature แล้ว ไม่แก้ pipeline หรือใช้ผล build runtime เก่าเป็นไฟล์แจก
