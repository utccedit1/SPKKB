"""Separate experimental tab, injected after the existing editor is assembled."""
UI = r'''
<div class="tabsec" id="tab_clilab">
 <div class="card">
  <h2>ตัดคลิปด้วย AI</h2>
  <p>ใช้ซับจาก CapCut เลือกช่วงสำคัญ แล้วนำคลิปที่ตัดกลับเข้าโปรเจกต์เดิม</p>
  <p style="opacity:.75">ก่อนเริ่ม: สร้างซับใน CapCut และบันทึกโปรเจกต์ · ข้อความซับจะส่งให้ UTCC วางแผน</p>
  <div id="cliLabSavedResults" aria-live="polite"></div>
  <button type="button" onclick="cliLabLoadResults()">ตรวจผลล่าสุดที่ยังไม่ใส่โปรเจกต์</button>
  <label for="cliLabInstruction">อยากได้คลิปแบบไหน?</label>
  <label for="cliLabPromptTemplate" style="display:block;margin:8px 0">แนวคลิป</label>
  <select id="cliLabPromptTemplate" style="width:100%;margin-bottom:8px" aria-describedby="cliLabPromptHint"></select>
  <p id="cliLabPromptHint" style="opacity:.75">เลือกแนวเพื่อเติมคำสั่งให้ทันที แก้ข้อความด้านล่างได้ หรือเลือกเขียนคำสั่งเอง · ความยาวและตัวเลือกสื่อใช้ค่าที่คุณตั้งไว้</p>
  <textarea id="cliLabInstruction" rows="3" style="width:100%;box-sizing:border-box" maxlength="4000" placeholder="เช่น เลือกประเด็นที่น่าสนใจ เปิดเรื่องให้น่าติดตาม แล้วจบให้ได้ใจความ"></textarea>
  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:12px 0">
   <span>ความยาว</span>
   <p style="opacity:.75">ระบุความยาวคลิปที่ต้องการเป็นวินาที เช่น 180–300 = 3–5 นาที · สูงสุด 10 นาที</p>
   <label>ความยาวต่ำสุด <input id="cliLabMin" type="number" min="5" max="600" value="30" style="width:75px"> วินาที</label>
   <label>ความยาวสูงสุด <input id="cliLabMax" type="number" min="5" max="600" value="45" style="width:75px"> วินาที</label>
  </div>
  <details style="margin:16px 0"><summary>ปรับแต่งเพิ่มเติม</summary>
   <p><label>รูปแบบ <select id="cliLabMode"><option value="story">จัดเรื่องหลายช่วง</option><option value="single">ตัดช่วงเดียว</option></select></label></p>
   <p id="cliLabModeHint" hidden>โหมดตัดช่วงเดียวใช้เฉพาะช่วงเวลาที่ AI เลือก ตัวเลือกจัดสไตล์ ซูม และสื่อประกอบใช้กับโหมดจัดเรื่องหลายช่วง</p>
   <p><label><input id="cliLabStyleCaps" type="checkbox" checked> จัดสไตล์ซับ</label>
   <select id="cliLabStyle" aria-label="สไตล์ซับ"><option value="bold">ตัวหนา / กล่องเข้ม</option><option value="clean">เรียบ / กล่องโปร่ง</option></select></p>
   <p><label><input id="cliLabAutoStock" type="checkbox"> ค้นและดาวน์โหลด B-roll จาก Artlist แล้วใส่ให้อัตโนมัติ</label></p>
   <p><label>ภาพประกอบ <select id="cliLabStockDensity"><option value="sparse">น้อย</option><option value="balanced" selected>พอดี</option><option value="rich">มาก</option></select></label> <label><input id="cliLabSpeakerPip" type="checkbox"> แสดงผู้พูดในกรอบเล็กบางช่วง</label></p>
   <label for="cliLabStockFolder">โฟลเดอร์เก็บสื่อของโปรเจกต์</label>
   <input id="cliLabStockFolder" style="width:100%;box-sizing:border-box" placeholder="เว้นว่าง = เก็บในโฟลเดอร์โปรเจกต์ CapCut">
   <button type="button" id="cliLabChooseStockFolder">เลือกโฟลเดอร์…</button><p id="cliLabStockDestination" role="status"></p>
   <div id="cliLabFolderPicker" hidden><label for="cliLabFolderPath">เรียกดูโฟลเดอร์</label><input id="cliLabFolderPath"><button type="button" id="cliLabFolderGo">ไป</button><button type="button" id="cliLabFolderUse">เลือกโฟลเดอร์นี้</button><button type="button" id="cliLabFolderCancel">ยกเลิก</button><div id="cliLabFolderList" style="max-height:220px;overflow:auto"></div></div>
   <p style="opacity:.75">เชื่อมบัญชีด้านบนก่อน · ไม่ใช้เครดิตสร้าง AI · จำนวนภาพปรับตามความยาวและเนื้อหา เลือกเพลงออนไลน์ได้ด้านล่าง หรือใช้ไฟล์เพลงของคุณ · หากภาพบางช่วงหาไม่ได้จะข้ามพร้อมแจ้งจำนวนที่ใส่จริง หากไม่มีภาพเลยจะแสดงคำเตือน ส่วนเพลงที่หาไม่ได้จะสร้างต่อโดยไม่มีเพลงและแจ้งในผลสรุป</p>
   <p><label><input id="cliLabCleanSpeech" type="checkbox" checked> ตัดคำลังเลที่จับเวลาได้ / ย่อช่วงเงียบ / ซูมต่อเนื่อง</label></p>
   <p><label><input id="cliLabEffects" type="checkbox" checked> สไตล์โซเชียล · ซูมมีจังหวะ / ข้อความเคลื่อนไหว / เสียงเน้นเบา ๆ</label></p>
   <label for="cliLabLibrary">คลังภาพประกอบอัตโนมัติ (ไม่บังคับ)</label><input id="cliLabLibrary" style="width:100%;box-sizing:border-box" placeholder="โฟลเดอร์ B-roll / ภาพ / PNG สติกเกอร์ ตั้งชื่อไฟล์เป็นคำที่พูด หรือใช้ library.json">
   <p style="opacity:.75">เลือกสื่อที่คำค้นตรงกับคำพูด เว้นจังหวะให้เห็นผู้พูดและปิดเสียงประกอบ · ยังไม่ค้นคลัง CapCut ออนไลน์</p>
   <label for="cliLabBroll">ภาพหรือคลิปประกอบ (ไม่บังคับ)</label><input id="cliLabBroll" style="width:100%;box-sizing:border-box" placeholder="ตำแหน่งไฟล์ภาพหรือคลิปในเครื่อง">
   <p><label><input id="cliLabAutoMusic" type="checkbox"> หาเพลงบรรเลงเบา ๆ ให้เข้ากับเนื้อหา (ใช้บัญชี Artlist ของคุณ และต้องเปิดค้นสื่อออนไลน์)</label></p>
   <label for="cliLabMusic">เพลงพื้นหลัง (ไม่บังคับ)</label><input id="cliLabMusic" style="width:100%;box-sizing:border-box" placeholder="ตำแหน่งไฟล์เพลงในเครื่อง">
   <p style="opacity:.75">คลิปประกอบปิดเสียงและปรับช่วงให้คลุมรอยตัด เสียงพูดปรับพีกประมาณ −4 dBFS (ช่วง −6 ถึง −2) และเพลง −18 dBFS พร้อมเฟด หากเลือกเพลงในเครื่องจะใช้เพลงนี้แทนเพลงออนไลน์</p>
  </details>
  <button id="cliLabPlanButton" class="primary" onclick="cliLab('plan')">1. วางแผนตัดคลิป</button>
  <button type="button" onclick="cliLab('enhance')">ปรับซับ / เติมภาพให้คลิปเดิม</button>
  <div id="cliLabPlanSection" hidden style="margin-top:20px">
   <h3>แผนตัดคลิป</h3>
   <p>แผนใช้สร้างคลิปได้ภายใน 1 ชั่วโมง ส่วนผลที่สร้างเสร็จแล้วไม่หมดอายุเพราะเวลา</p>
   <pre id="cliLabPlan" style="white-space:pre-wrap;overflow-wrap:anywhere" aria-live="polite"></pre>
   <details id="cliLabOverlayReview" hidden><summary>แก้ข้อความเปิดเรื่อง / ปิดท้าย</summary>
    <label for="cliLabHook">ข้อความเปิดเรื่อง</label><input id="cliLabHook" maxlength="120" style="width:100%;box-sizing:border-box">
    <label for="cliLabCTA">ข้อความปิดท้าย</label><input id="cliLabCTA" maxlength="120" style="width:100%;box-sizing:border-box">
   </details>
   <p><button id="cliLabApply" class="primary" onclick="cliLab('apply')" disabled>2. สร้างคลิปตามแผน</button></p>
  </div>
  <div id="cliLabInstallSection" hidden style="margin-top:20px">
   <h3>คลิปพร้อมใช้แล้ว</h3>
   <pre id="cliLabInstallReview" style="white-space:pre-wrap;overflow-wrap:anywhere" role="status"></pre>
   <pre id="cliLabCompletedReport" style="white-space:pre-wrap;overflow-wrap:anywhere" role="status"></pre>
   <p>บันทึกแล้วกลับหน้าหลัก CapCut ก่อนกดใช้คลิป ระบบจะสำรองไทม์ไลน์เดิมให้ย้อนกลับได้</p>
   <button id="cliLabInstall" class="primary" onclick="cliLab('install_commit')" disabled>3. ใช้คลิปนี้ในโปรเจกต์เดิม</button>
  </div>
  <button id="cliLabResume" type="button" hidden onclick="cliLabResumeJob()">ตรวจงานเดิมต่อ</button>
  <button id="cliLabPrepareResult" type="button" hidden onclick="cliLab('install_preview')">เตรียมนำคลิปเข้าอีกครั้ง</button>
  <button id="cliLabCancel" type="button" hidden onclick="cliLabCancelJob()">ยกเลิกงานที่กำลังทำ</button><pre id="cliLabResult" role="status" style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:300px;overflow:auto"></pre>
__RUN_MONITOR_UI__
  <details style="margin-top:24px;opacity:.85"><summary>เครื่องมือช่วยเหลือ</summary>
   <p id="cliLabStatus" role="status"></p><button type="button" onclick="cliLab('setup_alignment')">ติดตั้งเครื่องมือจับเวลาคำ (ดาวน์โหลดประมาณ 500 MB)</button>
   <button class="ghost" onclick="cliLab('status')">ตรวจความพร้อม</button>
   <button class="ghost" onclick="cliLab('ai_diagnostics')">รายงานการเชื่อมต่อ AI / Webhook</button>
   <button class="ghost" onclick="cliLab('diagnose')">ตรวจสุขภาพโปรเจกต์</button>
   <button class="ghost" onclick="cliLab('info')">ข้อมูลโปรเจกต์</button>
   <button class="ghost" onclick="cliLab('lint')">ตรวจข้อผิดพลาด</button>
   <p>หากมีผลตัดต่อที่สร้างไว้แล้ว เลือกใช้ต่อได้ที่นี่</p>
   <label for="cliLabResultFolder">โฟลเดอร์ผลตัดต่อ</label><input id="cliLabResultFolder" style="width:100%;box-sizing:border-box" placeholder="ตำแหน่งผลลัพธ์ที่สร้างไว้">
   <button class="ghost" onclick="cliLab('install_preview')">โหลดผลตัดต่อเดิม</button>
   <hr><p>เคลียร์ไฟล์ build รุ่นเก่าแบบย้อนคืนได้ โดยเก็บ 5 รุ่นล่าสุดและรุ่นที่กำลังใช้งาน ไม่แตะสื่อหรือโปรเจกต์</p>
   <button type="button" onclick="cliLabStorage('preview')">ตรวจพื้นที่ไฟล์เก่า</button><button id="cliStorageMove" type="button" hidden onclick="cliLabStorage('move')">ย้ายรายการที่ตรวจเข้า Trash</button><button id="cliStorageRestore" type="button" hidden onclick="cliLabStorage('restore')">กู้คืนไฟล์เก่า</button><pre id="cliStorageResult" style="white-space:pre-wrap"></pre>
  </details>
 </div>
</div>
'''
JS = r'''
<script>
(function(){
let plan=null,install=null,busy=false,waiting=false;
const q=id=>document.getElementById(id);
__RUN_MONITOR_JS__
function resetPlan(){plan=null;install=null;q('cliLabPrepareResult').hidden=true;q('cliLabApply').disabled=true;q('cliLabInstall').disabled=true;q('cliLabPlanSection').hidden=true;q('cliLabInstallSection').hidden=true;q('cliLabPlanButton').textContent='1. วางแผนตัดคลิป';q('cliLabPlanButton').className='primary';q('cliLabApply').hidden=false;}
q('cliLabInstruction').addEventListener('input',resetPlan);
__PROMPT_TEMPLATE_JS__
['cliLabMode','cliLabMin','cliLabMax','cliLabStyle','cliLabEffects','cliLabAutoStock','cliLabStockDensity','cliLabSpeakerPip','cliLabStockFolder','cliLabCleanSpeech','cliLabLibrary','cliLabStyleCaps','cliLabBroll','cliLabMusic','cliLabAutoMusic'].forEach(id=>q(id).addEventListener('change',resetPlan));
const storageKey='cliLabActiveJob:'+new URL(location.href).searchParams.get('workspace');
q('cliLabResultFolder').addEventListener('input',()=>{install=null;q('cliLabInstall').disabled=true;q('cliLabInstallSection').hidden=true;q('cliLabInstallReview').textContent='';});
function modeControls(){const single=q('cliLabMode').value==='single';q('cliLabModeHint').hidden=!single;['cliLabStyleCaps','cliLabStyle','cliLabAutoStock','cliLabStockDensity','cliLabSpeakerPip','cliLabStockFolder','cliLabCleanSpeech','cliLabEffects','cliLabLibrary','cliLabBroll','cliLabMusic','cliLabAutoMusic'].forEach(id=>q(id).disabled=busy||single);}
q('cliLabMode').addEventListener('change',modeControls);
function controls(on){busy=on;document.querySelectorAll('#tab_clilab button,#tab_clilab input,#tab_clilab select,#cliLabInstruction').forEach(e=>e.disabled=on);q('cliLabApply').disabled=on||!plan;q('cliLabInstall').disabled=on||!install;const cancel=q('cliLabCancel');if(cancel){cancel.hidden=!sessionStorage.getItem(storageKey);cancel.disabled=false;}q('cliLabResume').hidden=!waiting||on;q('cliLabResume').disabled=on;modeControls();}
async function post(body){const c=new AbortController(),timer=setTimeout(()=>c.abort(),150000);try{const r=await fetch('/api/cli_lab',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:c.signal});const j=await r.json();if(!r.ok||!j.ok){const e=Error(j.error||'ทำงานไม่สำเร็จ');e.definitive=[400,404].includes(r.status)||['job_not_found','project_mismatch'].includes(j.code);throw e;}return j;}finally{clearTimeout(timer);}}
function display(action,j){
 if(action==='install_preview'){
  q('cliLabPrepareResult').hidden=true;
  q('cliLabCompletedReport').textContent=j.review_notes||'';
  install=j.install_id;q('cliLabApply').hidden=true;q('cliLabInstallSection').hidden=false;q('cliLabInstallReview').textContent='ความยาวเดิม '+j.old_duration.toFixed(2)+' → คลิปใหม่ '+j.new_duration.toFixed(2)+' วินาที';
  q('cliLabResult').textContent=(j.review_notes||'').includes('⚠️ ยังไม่มี B-roll')?'สร้างคลิปแล้ว แต่ยังไม่มี B-roll · ตรวจรายงานก่อนนำเข้า':'พร้อมแล้ว กดใช้คลิปนี้ในโปรเจกต์เดิม';return;
 }
 if(action==='install_commit'){
  resetPlan();q('cliLabInstallReview').textContent='';
  q('cliLabResult').textContent=j.message;window.loadCaps?.();loadResults();return;
 }
 if(action==='status'){
  q('cliLabStatus').textContent='capcut-cli: '+(j.cli_available?'พบแล้ว':'ยังไม่ติดตั้ง')+' | UTCC: '+(j.utcc_configured?'ตั้งค่าแล้ว':'ยังไม่ตั้งค่า')+' | จับเวลาคำ: '+(j.alignment_ready?'พร้อม':'ต้องติดตั้งเครื่องมือ');
  q('cliLabResult').textContent='ตรวจการตั้งค่าเสร็จแล้ว';
 }else if(action==='plan'){
  plan=j.plan_id;q('cliLabPlanSection').hidden=false;q('cliLabPlanButton').textContent='วางแผนใหม่';q('cliLabPlanButton').className='ghost';
  q('cliLabOverlayReview').hidden=j.mode!=='story';
  if(j.mode==='story'){
   q('cliLabHook').value=j.hook;q('cliLabCTA').value=j.cta;
   const roles={hook:'เปิดเรื่อง',body:'เนื้อหา',conclusion:'สรุป'};
   q('cliLabPlan').textContent='รวม '+j.duration.toFixed(2)+' วินาที · '+j.cuts.length+' ช่วง'+(j.source_count?' · ใช้ '+j.source_count+' คลิปต้นฉบับ':'')+'\n\n'+j.cuts.map((c,i)=>(i+1)+'. '+roles[c.role]+' · ต้นฉบับ '+c.start.toFixed(2)+'–'+c.end.toFixed(2)+' วินาที\n'+c.text).join('\n\n')+'\n\nข้อความเน้น: '+((j.supers||[]).join(' · ')||'เลือกจากคำพูดตอนสร้างคลิป')+'\n\nเหตุผล: '+j.reason+'\n\nตัดคำลังเล: '+(j.clean_speech?'เปิด (เฉพาะคำที่จับเวลาได้ชัด)':'ปิด')+' · ภาพประกอบในคลัง: '+(j.visual_library||[]).length+' ไฟล์'+'\n\nสื่อออนไลน์: '+(j.auto_stock?(j.stock_requests||[]).map(r=>r.kind+': '+r.query).join(' · '):'ปิด')+'\n\nเอฟเฟกต์: '+(j.effects?'ซูม / เฟด':'ปิด')+' · สไตล์ซับ: '+(j.style_captions?j.style:'คงเดิม')+((j.warnings||[]).length?'\n\n'+j.warnings.join('\n'):'');
  }else q('cliLabPlan').textContent='ช่วง '+j.start+' – '+j.end+' วินาที ('+(j.end-j.start).toFixed(2)+' วินาที)\n'+j.reason;
  q('cliLabResult').textContent='อ่านแผน แล้วกดสร้างคลิปตามแผน';
 }else{
  if(['apply','enhance'].includes(action)){plan=null;install=null;q('cliLabApply').hidden=true;q('cliLabPlanSection').hidden=true;q('cliLabPrepareResult').hidden=false;q('cliLabResultFolder').value=j.destination||'';}
  q('cliLabResult').textContent=[j.destination,j.caption_count?'สร้างซับ '+j.caption_count+' ท่อน':'',j.note,j.output,j.warnings].filter(Boolean).join('\n\n')||'เสร็จแล้ว';
 }
}
async function finish(action,j){
 display(action,j);
 if(['apply','enhance'].includes(action)){
  q('cliLabResult').textContent='สร้างคลิปแล้ว กำลังเตรียมใช้ในโปรเจกต์เดิม…';
  const preview=await post(j.result_id?{action:'result_review',result_id:j.result_id}:{action:'install_preview',result_folder:j.destination});
  display('install_preview',preview);
  if(!preview.review_notes)q('cliLabCompletedReport').textContent=j.output||'';
 }
}
async function loadResults(){
 const area=q('cliLabSavedResults');
 try{
  const j=await post({action:'results'});area.textContent='';
  for(const row of j.results||[]){
   const line=document.createElement('div'),button=document.createElement('button');
   line.textContent='ผลล่าสุด · '+new Date(row.created*1000).toLocaleString('th-TH')+' · '+(row.operation==='enhance'?'ปรับคลิปเดิม':'ตัดคลิป')+' ';
   button.type='button';button.textContent='ตรวจและใช้ผลนี้ต่อ';
   button.onclick=async()=>{
    if(busy)return;controls(true);install=null;
    q('cliLabInstallSection').hidden=true;
    try{
     const review=await post({action:'result_review',result_id:row.result_id});
     q('cliLabResultFolder').value=row.destination;
     display('install_preview',review);
    }catch(e){q('cliLabResult').textContent=e.message;}
    finally{controls(false);}
   };
   line.appendChild(button);area.appendChild(line);
  }
  if(!(j.results||[]).length)area.textContent='ยังไม่มีผลที่รอนำเข้าของโปรเจกต์นี้';
 }catch(e){area.textContent='ตรวจผลล่าสุดไม่ได้: '+e.message+' · กดตรวจผลล่าสุดอีกครั้ง';}
}
window.cliLabLoadResults=loadResults;
async function watch(saved){
 let failures=0;
 for(;;){
  let j;try{j=await post({action:'job_status',job_id:saved.id});failures=0;}catch(e){if(e.definitive){sessionStorage.removeItem(storageKey);throw e;}if(++failures>=3)throw Error(e.message+' · กดตรวจงานเดิมต่อเมื่อเชื่อมต่อได้ งานยังอาจทำอยู่');await new Promise(r=>setTimeout(r,2000));continue;}
  renderRunProgress(j);
  q('cliLabResult').textContent='';
  if(j.state==='done'){sessionStorage.removeItem(storageKey);return j.result;}
  if(j.state==='failed'){sessionStorage.removeItem(storageKey);throw Error(j.error||'ทำงานไม่สำเร็จ');}
  await new Promise(r=>setTimeout(r,1500));
 }
}
// Storage is scoped by signed-in account and project on the server, not by tab.
async function stockSettings(save=false){
 const body={action:'stock_settings'};if(save)body.folder=q('cliLabStockFolder').value;
 const j=await post(body);q('cliLabStockFolder').value=j.folder||'';q('cliLabStockDestination').textContent='เก็บสื่อที่: '+j.destination;
}
q('cliLabStockFolder').addEventListener('change',()=>stockSettings(true).catch(e=>q('cliLabStockDestination').textContent=e.message));
let folderCurrent='';
async function browseStockFolder(path=''){
 const response=await fetch('/api/browse?path='+encodeURIComponent(path));const j=await response.json();
 if(!response.ok||j.error)throw Error(j.error||'เปิดโฟลเดอร์ไม่ได้');
 folderCurrent=j.path;q('cliLabFolderPath').value=j.path;const list=q('cliLabFolderList');list.replaceChildren();
 function row(name,path){const button=document.createElement('button');button.type='button';button.textContent=name;button.style.display='block';button.onclick=()=>browseStockFolder(path).catch(e=>q('cliLabStockDestination').textContent=e.message);list.appendChild(button);}
 if(j.parent)row('⬆ ขึ้นหนึ่งชั้น',j.parent);for(const entry of j.entries||[])if(entry.is_dir&&!entry.name.startsWith('.'))row('📁 '+entry.name,entry.path);
}
q('cliLabChooseStockFolder').onclick=()=>{q('cliLabFolderPicker').hidden=false;browseStockFolder(q('cliLabStockFolder').value).catch(e=>q('cliLabStockDestination').textContent=e.message);};
q('cliLabFolderGo').onclick=()=>browseStockFolder(q('cliLabFolderPath').value).catch(e=>q('cliLabStockDestination').textContent=e.message);
q('cliLabFolderCancel').onclick=()=>q('cliLabFolderPicker').hidden=true;
q('cliLabFolderUse').onclick=async()=>{if(!folderCurrent)return;q('cliLabStockFolder').value=folderCurrent;try{await stockSettings(true);resetPlan();q('cliLabFolderPicker').hidden=true;}catch(e){q('cliLabStockDestination').textContent=e.message;}};
stockSettings().catch(e=>q('cliLabStockDestination').textContent='ยังโหลดโฟลเดอร์ไม่ได้: '+e.message);
let cleanupId=null,storageBusy=false,undoIds=[];
const undoKey=storageKey+':cleanupUndo';
try{const saved=JSON.parse(sessionStorage.getItem(undoKey)||'[]');if(Array.isArray(saved))undoIds=saved.filter(v=>typeof v==='string'&&/^[a-f0-9]{32}$/.test(v));}catch(e){}
q('cliStorageRestore').hidden=!undoIds.length;
window.cliLabStorage=async function(action){
 if(storageBusy||busy||waiting)return;
 storageBusy=true;controls(true);
 const out=q('cliStorageResult');
 if(action==='preview'){cleanupId=null;q('cliStorageMove').hidden=true;}
 try{
  out.textContent='กำลังตรวจ…';
  const j=await post({action:'storage_'+action,cleanup_id:action==='restore'?undoIds[undoIds.length-1]:cleanupId});
  if(action==='preview'){
   cleanupId=j.cleanup_id;out.textContent=j.note+'\n\n'+j.files.map(f=>f.name+' · '+(f.size/1073741824).toFixed(2)+' GB').join('\n')+'\nรวม '+(j.total_bytes/1073741824).toFixed(2)+' GB';q('cliStorageMove').hidden=!j.files.length;
  }else{
   out.textContent=j.message;q('cliStorageMove').hidden=true;
   if(action==='move'){undoIds.push(j.cleanup_id);cleanupId=null;}else undoIds.pop();
   sessionStorage.setItem(undoKey,JSON.stringify(undoIds));
  }
 }catch(e){out.textContent=e.message;}
 finally{storageBusy=false;q('cliStorageRestore').hidden=!undoIds.length;controls(false);}
};
window.cliLabCancelJob=async function(){try{const saved=JSON.parse(sessionStorage.getItem(storageKey)||'null');if(!saved)return;const j=await post({action:'cancel',job_id:saved.id});q('cliLabResult').textContent=j.message;}catch(e){q('cliLabResult').textContent=e.message;}};
window.cliLab=async function(action){
 if(busy)return;
 if(sessionStorage.getItem(storageKey)){waiting=true;controls(false);q('cliLabResult').textContent='มีงานเดิมรอตรวจผล กดตรวจงานเดิมต่อก่อนเริ่มงานใหม่';return;}
 if(action==='plan'){
  const min=Number(q('cliLabMin').value),max=Number(q('cliLabMax').value);
  if(!q('cliLabInstruction').value.trim()){q('cliLabResult').textContent='บอกประเด็นหรือรูปแบบคลิปที่ต้องการก่อนวางแผน';q('cliLabInstruction').focus();return;}
  if(!Number.isFinite(min)||!Number.isFinite(max)||min<5||max>600||min>max){q('cliLabResult').textContent=min>max?'ความยาวต่ำสุดต้องไม่เกินความยาวสูงสุด เช่น 180 ถึง 300 วินาที':'ตั้งความยาวได้ 5–600 วินาที (สูงสุด 10 นาที)';return;}
 }
 if(action==='plan'){resetPlan();q('cliLabPlan').textContent='';q('cliLabProgressLog').textContent='';}
 controls(true);
 q('cliLabResult').textContent=action==='plan'?'กำลังตรวจซับ / เตรียมวางแผน…':['apply','enhance'].includes(action)?'กำลังสร้างคลิปตามแผน…':'กำลังตรวจ…';
 try{
  const body={action,instruction:q('cliLabInstruction').value,plan_id:plan,
   mode:q('cliLabMode').value,min_seconds:Number(q('cliLabMin').value),max_seconds:Number(q('cliLabMax').value),style:q('cliLabStyle').value,
   stock_folder:q('cliLabStockFolder').value,stock_density:q('cliLabStockDensity').value,speaker_pip:q('cliLabSpeakerPip').checked,auto_stock:q('cliLabAutoStock').checked,stock_provider:'artlist',clean_speech:q('cliLabCleanSpeech').checked,visual_library:q('cliLabLibrary').value,effects:q('cliLabEffects').checked,style_captions:q('cliLabStyleCaps').checked,broll:q('cliLabBroll').value,music:q('cliLabMusic').value,auto_music:q('cliLabAutoMusic').checked,
   text_style:typeof buildCfg==='function'?buildCfg():{},hook:q('cliLabHook').value,cta:q('cliLabCTA').value,result_folder:q('cliLabResultFolder').value,install_id:install};
  let j;
  if(['plan','apply','enhance','setup_alignment'].includes(action)){
   const started=await post({...body,action:'start',operation:action});const saved={id:started.job_id,action};sessionStorage.setItem(storageKey,JSON.stringify(saved));controls(true);j=await watch(saved);
  }else j=await post(body);
  await finish(action,j);
 }catch(e){if(action==='install_commit'){install=null;q('cliLabInstallSection').hidden=true;q('cliLabPrepareResult').hidden=false;}q('cliLabResult').textContent='ทำงานไม่สำเร็จ: '+e.message;}
 finally{waiting=!!sessionStorage.getItem(storageKey);controls(false);}
};
async function recover(){if(busy)return;let saved;try{saved=JSON.parse(sessionStorage.getItem(storageKey)||'null');}catch(e){sessionStorage.removeItem(storageKey);return;}if(!saved)return;if(typeof saved.id!=='string'||!['plan','apply','enhance','setup_alignment'].includes(saved.action)){sessionStorage.removeItem(storageKey);return;}controls(true);try{await finish(saved.action,await watch(saved));}catch(e){q('cliLabResult').textContent=e.message;}finally{waiting=!!sessionStorage.getItem(storageKey);controls(false);}}
window.cliLabResumeJob=recover;
recover();
loadResults();
})();
</script>
'''


from .cli_prompt_templates import JS as PROMPT_TEMPLATE_JS
JS = JS.replace('__PROMPT_TEMPLATE_JS__', PROMPT_TEMPLATE_JS)
from .cli_progress_ui import UI as RUN_UI, JS as RUN_JS
UI=UI.replace('__RUN_MONITOR_UI__',RUN_UI)
JS=JS.replace('__RUN_MONITOR_JS__',RUN_JS)

def inject(html):
    from .stock_accounts_ui import UI as STOCK_UI, JS as STOCK_JS
    nav = '<button class="ks-ni" onclick="ksSide(\'clilab\',this)"><span class="ni">✂️</span>ตัดคลิปด้วย AI</button>'
    marker = '<div class="ks-ni" onclick="ksSide(\'hist\',this)">'
    creative = '<div class="ks-ni" onclick="ksSide(\'chat\',this)">'
    if creative in html:marker=creative
    if marker not in html:
        raise RuntimeError('ไม่พบตำแหน่งเมนู CLI Lab')
    html = html.replace(marker, nav + marker, 1)
    html = html.replace('</div><!-- /tab_hist -->', '</div><!-- /tab_hist -->' + UI, 1)
    if 'id="tab_clilab"' not in html:
        raise RuntimeError('ไม่พบตำแหน่งแท็บ CLI Lab')
    html=html.replace('<label for="cliLabInstruction">',STOCK_UI+'<label for="cliLabInstruction">',1)
    return html.replace('</body>', JS + STOCK_JS + '</body>', 1)
