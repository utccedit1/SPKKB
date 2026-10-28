# Chrome Save dialog — 1.5.52

ผู้ใช้ยืนยันว่าเครื่องอื่นต้องกด Save ในหน้าต่างเลือกชื่อ/โฟลเดอร์ของ Chrome ไม่ใช่ปุ่มบน Artlist

ตรวจ worker.js: เริ่มดาวน์โหลดด้วยปุ่มของเว็บ และใช้ onDeterminingFilename เพื่อกำหนดโฟลเดอร์/uniquify; ไม่เรียก downloads.download และไม่กำหนด browser preference ส่วน FilenameSuggestion ไม่มี saveAs จึงไม่ควรเพิ่มตัวเลือกนี้ลง suggest เพื่ออ้างว่าข้าม dialog ได้

สาเหตุที่สอดคล้องกับอาการคือ Ask where to save each file before downloading ของ Chrome โปรไฟล์นั้นเปิดอยู่ ยังไม่ได้ตรวจเครื่องปลายทางโดยตรง ให้ปิดตัวเลือกนี้ใน chrome://settings/downloads ของโปรไฟล์ที่เชื่อม Artlist และคง Download location ตรงกับที่แอปอ่าน ไม่ต้องอัปเดตรุ่นเพื่อเปลี่ยน preference นี้

อ้างอิง: https://support.google.com/chrome/answer/95759 และ https://developer.chrome.com/docs/extensions/reference/api/downloads

ไม่มีการเปลี่ยน settings เครื่องนี้/เครื่องปลายทาง ไม่มีการส่งบัญชีหรือเริ่มดาวน์โหลดใหม่
