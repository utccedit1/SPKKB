"""Optional Artlist add-only mode beside the existing B-roll search tool."""
UI=r'''
<style>
.br-panel{margin-top:22px;padding:22px;border:1px solid #b8c8df;border-radius:18px;background:#f4f8ff;color:#172b49;box-shadow:0 6px 22px #193a6a14}.br-panel h3{margin:0 0 8px;font-size:20px;color:#173c70}.br-panel p{line-height:1.6}.br-guide{padding:12px 14px;border-left:4px solid #d29416;background:#fff5dc;color:#67440a;border-radius:8px}.br-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:14px 0}.br-status{padding:14px 16px;border-radius:12px;background:#e6efff;border:1px solid #95b8eb;color:#143e76;white-space:pre-wrap;overflow-wrap:anywhere;font-weight:600;line-height:1.6}.br-status.failed{background:#fff0ef;border-color:#e38c87;color:#8f1e1b}.br-status.done{background:#e1f6e9;border-color:#7bc69b;color:#125c39}.br-status.warning{background:#fff2d4;border-color:#dbad4a;color:#704900}.br-log-head{margin:18px 0 8px;display:flex;justify-content:space-between;font-weight:700;color:#193d71}.br-log{max-height:300px;min-height:82px;overflow:auto;background:#111e32;color:#e7f0ff;border:1px solid #344f75;border-radius:12px;padding:14px;font:13px/1.7 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}.br-summary{margin:10px 0;color:#244d80;font-weight:700}.br-note{display:block;margin-top:14px;color:#334f73;line-height:1.6}.br-panel button{margin:2px}.br-panel input{width:76px}
[data-theme=dark] .br-panel{background:#17253a;color:#e1eafa;border-color:#435a78}[data-theme=dark] .br-panel h3,[data-theme=dark] .br-log-head,[data-theme=dark] .br-summary{color:#b6d5ff}[data-theme=dark] .br-guide{background:#463616;color:#ffe7a8;border-color:#f1bd55}[data-theme=dark] .br-note{color:#c1d1e7}[data-theme=dark] .br-status{background:#193653;color:#d6eaff;border-color:#5c92c9}[data-theme=dark] .br-status.failed{background:#502a2b;color:#ffe1df;border-color:#e68c87}[data-theme=dark] .br-status.done{background:#174636;color:#d2ffe4;border-color:#63bd8d}[data-theme=dark] .br-status.warning{background:#503a15;color:#fff0c4;border-color:#d7ab4f}
</style>
<section class="br-panel" aria-label="เพิ่ม B-roll อัตโนมัติ">
 <h3>หาและใส่ B-roll อัตโนมัติ · Artlist</h3>
 <p>เพิ่มภาพประกอบปิดเสียงเป็นแทร็กใหม่ โดยคงรอยตัด ซับ เพลง เสียง โมชั่น และแทร็กเดิมไว้ทั้งหมด</p>
 <p class="br-guide"><strong>ก่อนนำเข้า:</strong> บันทึกงานและกลับหน้าหลัก CapCut จากนั้นตรวจรายการก่อนยืนยันใส่ B-roll</p>
 <div class="br-actions"><label>จำนวนภาพสูงสุด <input id="brollOnlyCount" type="number" min="1" max="30" value="8"></label>
 <button id="brollOnlyStart" class="primary" type="button">หาและเตรียม B-roll</button><button id="brollOnlyCancel" type="button" hidden>ยกเลิกงาน</button><button id="brollOnlyResume" type="button" hidden>ตรวจงานเดิมต่อ</button><button id="brollOnlyForget" type="button" hidden>ตรวจโปรเจกต์แล้ว · ล้างสถานะรอ</button><button id="brollOnlyApply" class="primary" type="button" hidden>ใส่เฉพาะ B-roll ในโปรเจกต์เดิม</button></div>
 <p><button type="button" onclick="ksSide('clilab')">ตรวจการเชื่อม Artlist / โฟลเดอร์สื่อ</button></p>
 <div id="brollOnlyStatus" class="br-status" role="status" aria-live="polite">พร้อมเริ่มงาน · เลือกจำนวนภาพแล้วกดหาและเตรียม B-roll</div>
 <div id="brollOnlySummary" class="br-summary">สถานะจะแสดงจำนวนภาพและขั้นตอนที่กำลังทำ</div>
 <div class="br-log-head"><span>บันทึกการทำงาน</span><span>เวลาของเครื่องนี้</span></div>
 <pre id="brollOnlyLog" class="br-log" role="log" aria-label="บันทึกงาน B-roll">รอเริ่มงาน</pre>
 <div class="br-actions"><button id="brollOnlyRepair" type="button">ตรวจซ่อมสื่อ B-roll ที่นำเข้าแล้ว</button><button id="brollOnlyFolder" type="button">เปิดโฟลเดอร์สื่อ B-roll</button></div>
 <div id="brollOnlySaved"></div>
 <small class="br-note">งานหลายภาพอาจใช้เกิน 30 นาที หากมีภาพเดิมทับช่วงนั้นจะข้าม หากหาไม่ได้จะรายงานตามจริง ไม่ตัดคลิปหรือปรับส่วนอื่นชดเชย</small>
</section>
'''

JS=r'''
<script>
(function(){
const q=id=>document.getElementById(id),key='brollOnlyJob:'+new URL(location.href).searchParams.get('workspace');
let busy=false,ticket=null;
const importKey=key+':import';
function status(message,state='running'){q('brollOnlyStatus').className='br-status '+state;q('brollOnlyStatus').textContent=message;}
function note(message){const box=q('brollOnlyLog');box.textContent+='\n['+new Date().toLocaleTimeString('th-TH')+'] '+message;box.scrollTop=box.scrollHeight;}
function renderLog(j){const box=q('brollOnlyLog'),rows=j.progress_log||[];const d=j.broll_summary||j;if(d.requested!==undefined)q('brollOnlySummary').textContent='พร้อม '+(d.prepared||0)+'/'+d.requested+' ภาพ · ดาวน์โหลด '+(d.downloaded||0)+' · ค้น '+(d.attempted||0)+' ครั้ง · ข้าม '+(d.skipped||0)+' ช่วง';else if(j.operation==='install_commit')q('brollOnlySummary').textContent='กำลังตรวจและนำผลเข้าโปรเจกต์';box.textContent=rows.map(r=>'['+new Date(r.time*1000).toLocaleTimeString('th-TH')+'] '+r.message).join('\n');if(j.broll_summary){const s=j.broll_summary;box.textContent+='\nสรุป: ตรวจคำค้น '+(s.attempted||0)+' ครั้ง · ข้าม '+(s.skipped||0)+' ช่วง · เตรียมได้ '+(s.prepared||0)+' ภาพ';}box.scrollTop=box.scrollHeight;}
function controls(on){busy=on;q('brollOnlyStart').disabled=on||!!sessionStorage.getItem(importKey);q('brollOnlyCount').disabled=on||!!sessionStorage.getItem(importKey);q('brollOnlyRepair').disabled=on||!!sessionStorage.getItem(importKey);q('brollOnlyApply').disabled=on||!ticket;q('brollOnlyCancel').hidden=!sessionStorage.getItem(key);q('brollOnlyResume').hidden=on||!(sessionStorage.getItem(key)||sessionStorage.getItem(importKey));q('brollOnlyForget').hidden=on||!sessionStorage.getItem(importKey);}
async function post(body){const c=new AbortController(),timer=setTimeout(()=>c.abort(),30000);try{const r=await fetch('/api/cli_lab',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:c.signal});const j=await r.json();if(!r.ok||!j.ok){const e=Error(j.error||'ทำงานไม่สำเร็จ');e.missing=r.status===404||j.code==='job_not_found';throw e;}return j;}finally{clearTimeout(timer);}}
async function saved(){try{const j=await post({action:'results'}),area=q('brollOnlySaved');area.textContent='';for(const row of j.results||[]){if(!['broll_only','broll_repair'].includes(row.operation))continue;const b=document.createElement('button');b.type='button';b.textContent='ตรวจผล B-roll ที่สร้างไว้ · '+new Date(row.created*1000).toLocaleString('th-TH');b.onclick=()=>prepare(row.result_id);area.appendChild(b);}}catch(e){q('brollOnlySaved').textContent='ตรวจผลที่สร้างไว้ไม่ได้: '+e.message;}}
async function prepare(id){if(busy)return;ticket=null;controls(true);q('brollOnlyApply').hidden=true;status('กำลังตรวจผลและไฟล์สื่อ');note('กำลังตรวจผลก่อนนำเข้า');try{const j=await post({action:'result_review',result_id:id});ticket=j.install_id;q('brollOnlyApply').textContent='ยืนยันใช้ผล B-roll ในโปรเจกต์เดิม';status((j.review_notes||'เตรียม B-roll แล้ว')+' · ตรวจรายการแล้วกดยืนยันเพื่อนำเข้า','warning');q('brollOnlyApply').hidden=false;}catch(e){status(e.message,'failed');}finally{controls(false);}}
async function watch(){let id;try{id=JSON.parse(sessionStorage.getItem(key)||'null')?.id;}catch(e){sessionStorage.removeItem(key);}if(!id){controls(false);return;}controls(true);let failures=0;try{for(;;){let j;try{j=await post({action:'job_status',job_id:id});failures=0;}catch(e){if(e.missing)sessionStorage.removeItem(key);if(e.missing||++failures>=3)throw e;await new Promise(r=>setTimeout(r,1500));continue;}
 renderLog(j);
 status(j.error||j.message||'กำลังหา B-roll',j.state==='failed'?'failed':j.state==='done'?'done':'running');
 if(['done','failed','cancelled'].includes(j.state)){sessionStorage.removeItem(key);if(j.state!=='done')throw Error(j.error||'งานหยุดแล้ว');const result=j.result;controls(false);await prepare(result.result_id);await saved();return;}
 await new Promise(r=>setTimeout(r,1500));}}catch(e){status(e.message,'failed');}finally{controls(false);}}
q('brollOnlyStart').onclick=async()=>{if(busy)return;if(sessionStorage.getItem(key)||sessionStorage.getItem(importKey)){status('มีงานเดิมรอตรวจผล กดตรวจงานเดิมต่อ','warning');return;}
 if(q('ksBrollKind').value!=='footage'){status('เลือกฟุตเทจ B-roll ก่อนใช้โหมดอัตโนมัติ มีมยังใช้หาไอเดียแบบเดิม','warning');return;}
 const count=Number(q('brollOnlyCount').value);if(!Number.isInteger(count)||count<1||count>30){status('เลือกจำนวนภาพ 1–30 ช็อต','warning');return;}
 controls(true);ticket=null;q('brollOnlyApply').hidden=true;q('brollOnlyLog').textContent='กำลังเริ่มงาน…';status('กำลังเริ่มงานและตรวจการเชื่อมต่อ');
 try{const j=await post({action:'start',operation:'broll_only',media_kind:'footage',max_shots:count,style:q('ksBrollStyle').value,persona:q('ksBrollPersona').value,per_line:q('ksBrollPerLine').checked});sessionStorage.setItem(key,JSON.stringify({id:j.job_id}));await watch();}catch(e){status(e.message,'failed');}finally{controls(false);}};
q('brollOnlyCancel').onclick=async()=>{try{const id=JSON.parse(sessionStorage.getItem(key)||'null')?.id;if(id)q('brollOnlyStatus').textContent=(await post({action:'cancel',job_id:id})).message;}catch(e){status(e.message,'failed');}};
q('brollOnlyResume').onclick=()=>sessionStorage.getItem(importKey)?watchImport():watch();
q('brollOnlyForget').onclick=()=>{if(busy)return;sessionStorage.removeItem(importKey);ticket=null;status('ล้างสถานะรอแล้ว · โปรดตรวจโปรเจกต์และประวัติก่อนเริ่มนำเข้าใหม่','warning');controls(false);};
q('brollOnlyRepair').onclick=async()=>{if(busy)return;ticket=null;controls(true);status('กำลังตรวจสื่อ B-roll ที่นำเข้าแล้ว');note('กำลังตรวจไฟล์สื่อเพื่อเตรียมซ่อม');try{const j=await post({action:'broll_repair_preview'});ticket=j.install_id;status((j.review_notes||'ตรวจสื่อแล้ว')+' · กดยืนยันเพื่อซ่อม','warning');q('brollOnlyApply').textContent='ยืนยันซ่อมสื่อ B-roll ในโปรเจกต์เดิม';q('brollOnlyApply').hidden=false;}catch(e){status(e.message,'failed');}finally{controls(false);}};
q('brollOnlyFolder').onclick=async()=>{try{q('brollOnlyStatus').textContent=(await post({action:'broll_media_folder'})).message;}catch(e){status(e.message,'failed');}};
async function watchImport(){const id=sessionStorage.getItem(importKey);if(!id)return;controls(true);q('brollOnlyCancel').hidden=true;let failures=0;try{for(;;){let j;try{j=await post({action:'job_status',job_id:id});failures=0;}catch(e){if(++failures>=3)throw e;await new Promise(r=>setTimeout(r,1500));continue;}renderLog(j);status(j.message||'กำลังนำเข้า');if(j.state==='done'){sessionStorage.removeItem(importKey);ticket=null;const result=j.result||{};status((result.warning?'⚠️ ':'ใส่เฉพาะ B-roll แล้ว · ')+(result.warning||result.message||'นำเข้าแล้ว'),result.warning?'warning':'done');note(result.warning||'นำเข้าเสร็จแล้ว');await saved();return;}if(j.state==='failed'){const check=await post({action:'install_check',install_id:id});sessionStorage.removeItem(importKey);status(check.state==='committed'?check.message:(j.error||'งานหยุด')+' · '+check.message,check.state==='committed'?'warning':'failed');note(q('brollOnlyStatus').textContent);return;}await new Promise(r=>setTimeout(r,1500));}}catch(e){status('ยังติดต่อสถานะนำเข้าไม่ได้ งานอาจยังดำเนินอยู่ · กดตรวจงานเดิมต่อ และตรวจโปรเจกต์ก่อนนำเข้าอีกครั้ง','warning');note('รอเชื่อมต่อเพื่อตรวจสถานะนำเข้า');}finally{controls(false);}}
q('brollOnlyApply').onclick=async()=>{if(busy||!ticket)return;const id=ticket;sessionStorage.setItem(importKey,id);q('brollOnlyApply').hidden=true;controls(true);q('brollOnlyCancel').hidden=true;status('กำลังเริ่มนำเข้าและตรวจโปรเจกต์');note('เริ่มตรวจและนำผลเข้าโปรเจกต์');try{await post({action:'start',operation:'install_commit',install_id:id});}catch(e){status('ยังไม่ได้รับสถานะเริ่มงาน กำลังตรวจงานเดิม','warning');}await watchImport();};
if(sessionStorage.getItem(importKey))watchImport();else watch();saved();
})();
</script>
'''


def inject(html):
    marker='<div id="ksBrollOut" style="margin-top:12px"></div>'
    if marker not in html:raise ValueError('ไม่พบจุดวางโหมด B-roll อัตโนมัติ')
    return html.replace(marker,marker+UI,1).replace('</body>',JS+'</body>',1)
