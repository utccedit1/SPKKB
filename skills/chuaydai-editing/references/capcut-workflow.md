# ใช้กับ CapCut และช่วยด้วยจ้า

## สำรวจและแยกเวลา

อ่านคำสั่ง workspace, ARCHITECTURE.md, TASK_PHASES.md และซอร์สที่เกี่ยวข้องในตำแหน่งปัจจุบันก่อนทำงานในโปรเจกต์นี้ ไฟล์อ้างอิงไม่ใช่สิทธิ์ส่งข้อมูลจริงไป AI/stock หรือเผยแพร่ skill/สื่อ

ตรวจ source, สื่อที่ active timeline ใช้, selected audio, track visibility, compound/multicam และสถานะ editor สร้างงานในสำเนา ไม่แก้ bundle/build แทนซอร์ส ไม่เอา ID/path/cache/resource ของโปรเจกต์อ้างอิงมาวางข้ามงานตรง ๆ

เวลา nested ต้องพิจารณาแต่ละ instance: ตัดช่วง child กับ source slice ของ parent ก่อน แล้วแปลงเวลาโดย speed และ target start ของทุกชั้น เช่น parent เริ่ม 20 s ใช้ child 8–12 s ที่ speed=1: child text ที่ 10 s เริ่มที่ 22 s; text ที่ 2 s จะไม่เห็นถ้าจบก่อน 8 s แต่ถ้าทอดมาถึง slice ให้เอาเฉพาะส่วนทับ ห้ามนับนิยาม child ทั้งชุดเป็นผลบนจอ ถ้ามี reverse/speed curve/schema ที่ยังอ่านไม่ได้ ให้ระบุข้อจำกัดและตรวจใน CapCut

## จุดเชื่อมที่มีจริงในซอร์สปัจจุบัน

เส้นทางด้านล่างสัมพันธ์กับ root ของแอป ไม่ใช่ dependency ที่ skill ฝังมา อ่านโค้ดปัจจุบันก่อนเรียกใช้ ไม่มี API “apply skill” ในแอปจากการติดตั้ง skill นี้

| หน้าที่ | โมดูลใต้ app/ks |
|---|---|
| อ่านซับจริง/แผน story/รอยต่อ | cli_lab.py, cli_lab_story.py, cli_lab_planning.py |
| แยกบทพูดจาก overlay | caption_roles.py |
| วลีซับ/ข้อความเน้น | cli_lab_presentation.py, text_layout.py |
| ฟอนต์และแบรนด์จาก config | cli_lab_typography.py, cli_lab_brand_style.py, caption_style.py |
| โมชั่น/สไตล์โซเชียล | timeline_motion.py, cli_lab_social.py |
| nested และเวลาเสียง | cli_lab_nested.py, cli_lab_alignment.py |
| เสียง/สื่อ stock | audio_levels.py, stock_polish.py, stock_project.py |
| สำเนา/ตรวจนำเข้า/กู้คืน | cli_lab_commit.py, cli_results.py, event_timeline.py, apply_guard.py |

โมดูลเหล่านี้เป็นเครื่องมือย่อย ไม่ใช่ style engine ที่ถอดทุก compound/effect ได้แล้ว ฟอนต์ fallback ไม่เท่ากับฟอนต์อ้างอิง ต้องแจ้งเมื่อมีผลต่อหน้าตา

## เงื่อนไขงานตัด

- ใช้ซับ CapCut พร้อมเวลา ไม่ถอดบทใหม่แทนโดยเงียบ ๆ รายคำ confidence ต่ำให้คงเสียง/ขอบเดิมและตรวจฟัง ไม่ลบคำจากเวลาที่เดา
- ภาพดำอาจเป็นองค์ประกอบตั้งใจของงานเสียง ตรวจบริบทก่อนเลือกกราฟิก ไม่ถือว่ามี speaker footage; speaker PiP เปิดเฉพาะเมื่อผู้ใช้เลือก
- effect/resource ตรวจการมีอยู่และสิทธิ์บนเครื่องเป้าหมาย หากไม่มี เสนอหรือทำ fallback ภายในขอบเขตงานพร้อมบอกความต่าง ไม่อ้างทำเหมือนเดิมสำเร็จ
- คำค้น stock เป็นอังกฤษและต้องสัมพันธ์เนื้อหา ใช้บัญชีเจ้าของงาน ไม่ถือว่าไฟล์ preview เป็นสื่อใช้งานจริง
- พีกพูด −4 dBFS และเพลง −18 dBFS เป็นเป้าหมายระบบที่มีอยู่ ไม่ใช่ค่า volume fader หรือ LUFS และไม่ใช่ค่าที่วัดจาก reference ทั้งสาม คง mute/fade/กราฟเดิมตามสัญญางาน
- นำเข้าผ่าน owner/project/source/output hash, media checks, lock, backup, mirror transaction และ rollback เดิม ผลสร้างแล้วไม่หมดอายุเพราะเวลา; ไม่ส่ง commit ซ้ำเพื่อแก้สถานะไม่ชัด

## ทดลองให้รู้ว่าคล้ายตรงไหน

เริ่มช่วงตัวแทน 10–20 วินาทีในสำเนาเมื่อยังไม่เคยพิสูจน์ลูกเล่นนั้น ตรวจข้อความ/โมชั่น/เสียงเทียบ reference ที่มีสื่อพร้อม แล้วลองกับเนื้อหาใหม่ ประเมินความเข้าใจเรื่อง ความครบของคำพูด การอ่าน จังหวะ ความเหมาะสมของภาพ/เสียง และสิ่งที่ผู้ใช้ต้องแก้ ผลที่ตรวจแต่ JSON ยังไม่ผ่านภาพ/เสียง native และห้ามอ้างว่าแทนคนตัดได้ครบ

ส่งมอบผลที่สร้างจริงพร้อมรายการที่ตรวจแล้วและยังไม่ตรวจ การนำเข้า/เผยแพร่/อัปเดตแอปทำตามขอบเขตคำขอครั้งนั้น การสร้าง skill ไม่ให้สิทธิ์ทำทุกขั้นกับทุกโปรเจกต์ถาวร
