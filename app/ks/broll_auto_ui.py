"""Optional Artlist add-only mode beside the existing B-roll search tool."""
UI=r'''
<section style="margin-top:20px;border-top:1px solid var(--line);padding-top:16px" aria-label="เพิ่ม B-roll อัตโนมัติ">
 <h3>หาและใส่ B-roll อัตโนมัติ · Artlist</h3>
 <p>เพิ่มภาพประกอบปิดเสียงเป็นแทร็กใหม่ โดยคงรอยตัด ซับ เพลง เสียง โมชั่น และแทร็กเดิมไว้ทั้งหมด ใช้ซับปัจจุบันและบัญชี Artlist ของคุณ</p>
 <p>1. หาและเตรียมภาพ → 2. ตรวจรายการแล้วใส่ B-roll · บันทึกและกลับหน้าหลัก CapCut ก่อนกดใส่</p>
 <label>จำนวนภาพสูงสุด <input id="brollOnlyCount" type="number" min="1" max="30" value="8" style="width:80px"></label>
 <button id="brollOnlyStart" type="button">หาและเตรียม B-roll</button>
 <button id="brollOnlyCancel" type="button" hidden>ยกเลิกงาน</button>
 <button id="brollOnlyResume" type="button" hidden>ตรวจงานเดิมต่อ</button>
 <button id="brollOnlyApply" type="button" hidden>ใส่เฉพาะ B-roll ในโปรเจกต์เดิม</button>
 <p><button type="button" onclick="ksSide('clilab')">ตรวจการเชื่อม Artlist / โฟลเดอร์สื่อ</button></p>
 <pre id="brollOnlyStatus" role="status" style="white-space:pre-wrap"></pre>
 <p><button id="brollOnlyRepair" type="button">ตรวจซ่อมสื่อ B-roll ที่นำเข้าแล้ว</button> <button id="brollOnlyFolder" type="button">เปิดโฟลเดอร์สื่อ B-roll</button></p>
 <pre id="brollOnlyLog" role="log" aria-label="บันทึกงาน B-roll" style="max-height:300px;overflow:auto;white-space:pre-wrap;border:1px solid var(--line);padding:10px"></pre>
 <div id="brollOnlySaved"></div>
 <small>งานหลายภาพอาจใช้เกิน 30 นาที โดยตรวจเวลารอ AI และดาวน์โหลดแยกแต่ละขั้น หากมีภาพเดิมทับช่วงนั้นจะข้าม หากหาไม่ได้จะรายงานตามจริง ไม่ตัดคลิปหรือปรับส่วนอื่นชดเชย</small>
</section>
'''
JS=r'''
<script>
(function(){
const q=id=>document.getElementById(id),key='brollOnlyJob:'+new URL(location.href).searchParams.get('workspace');
let busy=false,ticket=null;
function renderLog(j){const box=q('brollOnlyLog'),rows=j.progress_log||[];box.textContent=rows.map(r=>'['+new Date(r.time*1000).toLocaleTimeString('th-TH')+'] '+r.message).join('\n');if(j.broll_summary){const s=j.broll_summary;box.textContent+='\nสรุป: ตรวจคำค้น '+(s.attempted||0)+' ครั้ง · ข้าม '+(s.skipped||0)+' ช่วง · เตรียมได้ '+(s.prepared||0)+' ภาพ';}box.scrollTop=box.scrollHeight;}
function controls(on){busy=on;q('brollOnlyStart').disabled=on;q('brollOnlyCount').disabled=on;q('brollOnlyApply').disabled=on||!ticket;q('brollOnlyCancel').hidden=!sessionStorage.getItem(key);q('brollOnlyResume').hidden=on||!sessionStorage.getItem(key);}
async function post(body){const c=new AbortController(),timer=setTimeout(()=>c.abort(),30000);try{const r=await fetch('/api/cli_lab',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:c.signal});const j=await r.json();if(!r.ok||!j.ok){const e=Error(j.error||'ทำงานไม่สำเร็จ');e.missing=r.status===404||j.code==='job_not_found';throw e;}return j;}finally{clearTimeout(timer);}}
async function saved(){try{const j=await post({action:'results'}),area=q('brollOnlySaved');area.textContent='';for(const row of j.results||[]){if(!['broll_only','broll_repair'].includes(row.operation))continue;const b=document.createElement('button');b.type='button';b.textContent='ตรวจผล B-roll ที่สร้างไว้ · '+new Date(row.created*1000).toLocaleString('th-TH');b.onclick=()=>prepare(row.result_id);area.appendChild(b);}}catch(e){q('brollOnlySaved').textContent='ตรวจผลที่สร้างไว้ไม่ได้: '+e.message;}}
async function prepare(id){if(busy)return;ticket=null;controls(true);q('brollOnlyApply').hidden=true;try{const j=await post({action:'result_review',result_id:id});ticket=j.install_id;q('brollOnlyApply').textContent='ยืนยันใช้ผล B-roll ในโปรเจกต์เดิม';q('brollOnlyStatus').textContent=j.review_notes||'เตรียม B-roll แล้ว';q('brollOnlyApply').hidden=false;}catch(e){q('brollOnlyStatus').textContent=e.message;}finally{controls(false);}}
async function watch(){let id;try{id=JSON.parse(sessionStorage.getItem(key)||'null')?.id;}catch(e){sessionStorage.removeItem(key);}if(!id){controls(false);return;}controls(true);let failures=0;try{for(;;){let j;try{j=await post({action:'job_status',job_id:id});failures=0;}catch(e){if(e.missing)sessionStorage.removeItem(key);if(e.missing||++failures>=3)throw e;await new Promise(r=>setTimeout(r,1500));continue;}
 renderLog(j);
 q('brollOnlyStatus').textContent=j.error||j.message||'กำลังหา B-roll';
 if(['done','failed','cancelled'].includes(j.state)){sessionStorage.removeItem(key);if(j.state!=='done')throw Error(j.error||'งานหยุดแล้ว');const result=j.result;controls(false);await prepare(result.result_id);await saved();return;}
 await new Promise(r=>setTimeout(r,1500));}}catch(e){q('brollOnlyStatus').textContent=e.message;}finally{controls(false);}}
q('brollOnlyStart').onclick=async()=>{if(busy)return;if(sessionStorage.getItem(key)){q('brollOnlyStatus').textContent='มีงานเดิมรอตรวจผล กดตรวจงานเดิมต่อ';return;}
 if(q('ksBrollKind').value!=='footage'){q('brollOnlyStatus').textContent='เลือกฟุตเทจ B-roll ก่อนใช้โหมดอัตโนมัติ มีมยังใช้หาไอเดียแบบเดิม';return;}
 const count=Number(q('brollOnlyCount').value);if(!Number.isInteger(count)||count<1||count>30){q('brollOnlyStatus').textContent='เลือกจำนวนภาพ 1–30 ช็อต';return;}
 controls(true);ticket=null;q('brollOnlyApply').hidden=true;q('brollOnlyLog').textContent='กำลังเริ่มงาน…';
 try{const j=await post({action:'start',operation:'broll_only',media_kind:'footage',max_shots:count,style:q('ksBrollStyle').value,persona:q('ksBrollPersona').value,per_line:q('ksBrollPerLine').checked});sessionStorage.setItem(key,JSON.stringify({id:j.job_id}));await watch();}catch(e){q('brollOnlyStatus').textContent=e.message;}finally{controls(false);}};
q('brollOnlyCancel').onclick=async()=>{try{const id=JSON.parse(sessionStorage.getItem(key)||'null')?.id;if(id)q('brollOnlyStatus').textContent=(await post({action:'cancel',job_id:id})).message;}catch(e){q('brollOnlyStatus').textContent=e.message;}};
q('brollOnlyResume').onclick=watch;
q('brollOnlyRepair').onclick=async()=>{if(busy)return;ticket=null;controls(true);try{const j=await post({action:'broll_repair_preview'});ticket=j.install_id;q('brollOnlyStatus').textContent=j.review_notes;q('brollOnlyApply').textContent='ยืนยันซ่อมสื่อ B-roll ในโปรเจกต์เดิม';q('brollOnlyApply').hidden=false;}catch(e){q('brollOnlyStatus').textContent=e.message;}finally{controls(false);}};
q('brollOnlyFolder').onclick=async()=>{try{q('brollOnlyStatus').textContent=(await post({action:'broll_media_folder'})).message;}catch(e){q('brollOnlyStatus').textContent=e.message;}};
q('brollOnlyApply').onclick=async()=>{if(busy||!ticket)return;controls(true);try{const j=await post({action:'install_commit',install_id:ticket});ticket=null;q('brollOnlyApply').hidden=true;q('brollOnlyStatus').textContent='ใส่เฉพาะ B-roll แล้ว · '+j.message;await saved();}catch(e){ticket=null;q('brollOnlyApply').hidden=true;q('brollOnlyStatus').textContent=e.message+' · ตรวจผลที่สร้างไว้อีกครั้ง';}finally{controls(false);}};
watch();saved();
})();
</script>
'''


def inject(html):
    marker='<div id="ksBrollOut" style="margin-top:12px"></div>'
    if marker not in html:raise ValueError('ไม่พบจุดวางโหมด B-roll อัตโนมัติ')
    return html.replace(marker,marker+UI,1).replace('</body>',JS+'</body>',1)
