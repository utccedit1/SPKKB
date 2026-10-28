"""Editorial briefs only: presets never enable downloads or change cut duration."""
import json

TEMPLATES = [
 ('social','แนะนำ · คลิปโซเชียลชวนดูต่อ','เลือกประเด็นที่น่าสนใจที่สุดจากคำพูดจริง เปิดด้วยคำถามหรือประโยคที่ชวนดูต่อ แล้วเรียงเหตุผลและตัวอย่างให้เข้าใจง่าย จบให้ได้ข้อคิดชัดเจน ตัดคำซ้ำและคำลังเลเฉพาะที่จับเวลาได้ รักษาบริบทและความหมายของผู้พูด ไม่แต่งคำพูด ไม่พาดหัวเกินจริง ให้จังหวะกระชับแต่ไม่เร่งจนฟังไม่ทัน'),
 ('knowledge','ให้ความรู้ / อธิบายเรื่องยาก','เลือกประเด็นความรู้หลักหนึ่งเรื่อง เปิดให้เห็นว่าคนดูจะได้รู้อะไร อธิบายจากง่ายไปยากโดยใช้เหตุผลและตัวอย่างจากต้นฉบับ เก็บคำจำกัดความและเงื่อนไขที่จำเป็น จบด้วยข้อสรุปที่นำไปใช้ได้ รักษาความถูกต้องและบริบท ไม่แต่งข้อมูลหรือคำพูด'),
 ('interview','สัมภาษณ์ / พอดแคสต์','เลือกคำถามและคำตอบที่มีสาระหรือมุมมองน่าสนใจ เก็บคำถามหรือบริบทให้รู้ว่าผู้พูดกำลังตอบเรื่องอะไร เรียงคำตอบกับตัวอย่างให้ต่อเนื่อง หากมีหลายคนให้รักษาความสัมพันธ์ของบทสนทนา ไม่ตัดให้คนหนึ่งดูเหมือนพูดสิ่งที่ไม่ได้หมายความ จบประเด็นให้ครบ'),
 ('story','เล่าเรื่อง / ประสบการณ์','เลือกเรื่องที่มีสถานการณ์ ปัญหา จุดเปลี่ยน และผลลัพธ์ เปิดด้วยเหตุการณ์หรือประเด็นชวนสงสัยจากต้นฉบับ แล้วเล่าให้ติดตามง่าย เก็บรายละเอียดที่ช่วยเข้าใจอารมณ์และเหตุผล จบด้วยบทเรียนของผู้พูด ไม่สลับเหตุการณ์จนความหมายเปลี่ยน และไม่แต่งข้อสรุปแทนผู้พูด'),
 ('tips','เคล็ดลับ / How-to','เลือกคำแนะนำที่ทำตามได้จริง เปิดด้วยปัญหาที่คำแนะนำนี้ช่วยแก้ เรียงขั้นตอนหรือเคล็ดลับตามลำดับที่เข้าใจง่าย ใช้เฉพาะวิธีและข้อควรระวังที่มีในต้นฉบับ จบด้วยสิ่งที่คนดูเริ่มทำได้ ไม่สร้างขั้นตอน ตัวเลข หรือผลลัพธ์ที่ต้นฉบับไม่ได้บอก'),
 ('business','ธุรกิจ / วิเคราะห์ / สรุปประเด็น','เลือกข้อค้นพบหรือปัญหาธุรกิจที่สำคัญ เปิดด้วยประเด็นหลัก แล้วนำเหตุผล หลักฐาน และตัวอย่างจากต้นฉบับมาสนับสนุน แยกความคิดเห็นออกจากข้อเท็จจริง รักษาตัวเลข เงื่อนไข และคำอธิบายที่จำเป็น ใช้น้ำเสียงน่าเชื่อถือ จบด้วยข้อสรุปที่ผู้พูดรองรับไว้'),
 ('product','แนะนำสินค้า / บริการ','เลือกปัญหาของผู้ใช้ ประโยชน์ จุดเด่น และตัวอย่างการใช้งานที่พูดไว้จริง เปิดให้รู้ว่าสิ่งนี้เหมาะกับใคร แล้วอธิบายอย่างเป็นธรรมชาติ เก็บข้อจำกัดที่สำคัญ จบด้วยคำแนะนำหรือคำชวนที่มีอยู่ในต้นฉบับเท่านั้น ไม่แต่งราคา โปรโมชั่น คำรับประกัน หรือผลลัพธ์'),
 ('highlight','ไฮไลต์ / ประโยคคม','เลือกช่วงคำพูดที่โดดเด่น เข้าใจได้ด้วยตัวเอง และมีข้อคิดหรือมุมมองชัดเจน เก็บประโยคก่อนหน้าที่จำเป็นต่อบริบท ลดส่วนซ้ำให้กระชับ จบประโยคให้สมบูรณ์ ไม่ต่อคำจากคนละบริบทให้เป็นคำกล่าวใหม่ และไม่สร้างดราม่าเกินเนื้อหา'),
 ('custom','เขียนคำสั่งเอง',''),
]

JS = r'''
const promptTemplates=__TEMPLATES__;
const promptSelect=q('cliLabPromptTemplate'),promptInput=q('cliLabInstruction');
const promptKey='cliLabPromptDraft:'+new URL(location.href).searchParams.get('workspace');
let promptDrafts={},promptSelected='social';
try{const saved=JSON.parse(sessionStorage.getItem(promptKey)||'null');if(saved&&promptTemplates.some(t=>t[0]===saved.selected)){promptSelected=saved.selected;if(saved.drafts&&typeof saved.drafts==='object')promptDrafts=saved.drafts;}}catch(e){}
for(const [value,label] of promptTemplates){const option=document.createElement('option');option.value=value;option.textContent=label;promptSelect.appendChild(option);}
function promptText(key){const draft=promptDrafts[key];return typeof draft==='string'?draft.slice(0,4000):promptTemplates.find(t=>t[0]===key)[2];}
function savePromptDraft(){promptDrafts[promptSelected]=promptInput.value;try{sessionStorage.setItem(promptKey,JSON.stringify({selected:promptSelected,drafts:promptDrafts}));}catch(e){}}
promptSelect.value=promptSelected;promptInput.value=promptText(promptSelected);
promptSelect.addEventListener('change',()=>{savePromptDraft();promptSelected=promptSelect.value;promptInput.value=promptText(promptSelected);savePromptDraft();resetPlan();});
promptInput.addEventListener('input',savePromptDraft);
'''.replace('__TEMPLATES__',json.dumps(TEMPLATES,ensure_ascii=False))
