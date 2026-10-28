"""Guided account setup. Credentials remain in the owner's browser."""
UI='''
<details class="card" style="margin:12px 0" id="stockAccountsPanel"><summary>บัญชีคลังสื่อ · Artlist / Envato</summary>
 <p>เชื่อมครั้งแรกแล้วทดสอบไฟล์จริงก่อนเริ่มตัด หลังจากนั้นใช้งานผ่านช่วยด้วยจ้าได้เลย โดยเปิด Chrome โปรไฟล์ที่เชื่อมไว้ คุณเลือกใช้ Chrome ที่ล็อกอินอยู่แล้วได้ ไม่จำเป็นต้องสร้างโปรไฟล์ใหม่ ครั้งแรก Chrome อาจถามให้อนุญาต Artlist ดาวน์โหลดหลายไฟล์ ต้องอนุญาตบน Chrome ก่อนจึงจะดาวน์โหลดต่อเนื่องได้</p>
 <label>บริการ <select id="stockAccountProvider"><option value="artlist">Artlist</option><option value="envato">Envato · ยังไม่รองรับดาวน์โหลดอัตโนมัติ</option></select></label>
 <label>Chrome สำหรับเชื่อมครั้งแรก <select id="stockBrowserMode"><option value="existing">Chrome ที่ใช้ประจำ · ใช้บัญชีที่คุณล็อกอินไว้</option><option value="dedicated">โปรไฟล์แยกของแอป · สำหรับคนที่เชื่อมแบบเดิม</option></select></label>
 <ol id="stockSetupSteps"><li id="stockStep1">ติดตั้ง Stock Bridge ใน Chrome โปรไฟล์ที่คุณเลือก</li><li id="stockStep2">วางรหัสเชื่อมในส่วนขยาย</li><li id="stockStep3">ล็อกอินบัญชีของคุณบนเว็บ</li></ol>
 <button type="button" id="stockMainButton" onclick="stockAccounts('start')">เชื่อมบัญชี / ตรวจการเชื่อม</button>
 <button type="button" onclick="stockAccounts('test_download')">ทดสอบดาวน์โหลดจริง 1 ไฟล์</button>
 <button type="button" onclick="stockAccounts('authorize_downloads')">เลือกโฟลเดอร์ดาวน์โหลดให้แอปอ่าน</button>
 <p style="opacity:.75">หากเปิดสิทธิ์แล้วแต่ยังอ่านไม่ได้หลังอัปเดต ให้ใช้ปุ่มเลือกโฟลเดอร์ แล้วเลือกโฟลเดอร์เดียวกับ Downloads ของ Chrome</p>
 <p style="opacity:.75">ปุ่มทดสอบใช้ประเภทสื่อที่เลือกในรายละเอียดด้านล่าง และไม่แก้โปรเจกต์</p>
 <p id="stockAccountStatus" role="status" aria-live="polite">ใช้บัญชีของใครของมัน ไม่ต้องส่งรหัสผ่านให้แอปหรือผู้แจก</p>
 <div id="stockPairingSection" hidden>
  <h4>1 · ติดตั้งส่วนขยายครั้งแรก</h4><p>เปิดโหมดนักพัฒนาบนหน้า Extensions ที่เปิดให้ แล้วกด Load unpacked เลือกโฟลเดอร์ด้านล่าง</p>
  <pre id="stockExtensionFolder" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre><button type="button" onclick="stockCopy('stockExtensionFolder')">คัดลอกที่อยู่โฟลเดอร์</button>
  <h4>2 · เชื่อมกับแอปนี้</h4><p>เปิดส่วนขยาย “ช่วยด้วยจ้า · Stock Bridge” บนแถบ Chrome วางรหัสนี้ แล้วกด “เชื่อมและเปิดเว็บ”</p>
  <textarea id="stockPairingCode" readonly rows="2" style="width:100%" aria-label="รหัสเชื่อมส่วนขยายเฉพาะเครื่อง"></textarea><button type="button" onclick="stockCopy('stockPairingCode')">คัดลอกรหัสเชื่อม</button>
  <h4>3 · เข้าบัญชีของคุณ</h4><p>ล็อกอินและยืนยัน CAPTCHA ใน Chrome ด้วยตัวเอง หน้านี้จะตรวจสถานะให้โดยอัตโนมัติ</p>
 </div>
 <details><summary>ตรวจสอบหรือยกเลิกการเชื่อม</summary>
 <label>โฟลเดอร์ดาวน์โหลดของ Chrome (กรอกเฉพาะเมื่อเปลี่ยนจาก Downloads)</label><input id="stockDownloadRoot" placeholder="เช่น /Volumes/Media/Downloads" style="width:100%"><button type="button" onclick="stockAccounts('download_root')">บันทึกโฟลเดอร์ดาวน์โหลด</button>
 <button type="button" onclick="stockAccounts('check')">ตรวจบัญชีหลังล็อกอิน</button>
 <button type="button" onclick="stockAccounts('connect')">แสดงขั้นตอนเชื่อมใหม่</button>
 <p>ทดสอบดาวน์โหลดสื่อตัวอย่างหนึ่งไฟล์ โดยไม่แก้โปรเจกต์</p><label>สื่อทดสอบ <select id="stockTestKind"><option value="broll">คลิปวิดีโอ</option><option value="music">เพลง</option></select></label><button type="button" onclick="stockAccounts('test_download')">ทดสอบดาวน์โหลด</button>
 <p id="stockTestResult" role="status" aria-live="polite"></p>
 <p><button type="button" class="ghost" onclick="stockAccounts('disconnect')">ยกเลิกสิทธิ์ส่วนขยายบนเครื่องนี้</button></p></details>
 <p style="opacity:.75">Artlist รองรับวิดีโอและเพลง · Envato ยังไม่รองรับดาวน์โหลดอัตโนมัติ · ต้องติดตั้งส่วนขยายเองครั้งแรก แอปไม่มีรหัสผ่านหรือบัญชีของผู้แจก การยกเลิกสิทธิ์ไม่ได้ออกจากบัญชีเว็บ · เก็บที่มาสื่อให้ แต่ยังไม่ตรวจใบอนุญาตหรือรับรองการไม่มีลายน้ำจากภาพจริง</p>
</details>
'''
JS=r'''
<script>
(()=>{
 let working=false;
 const q=id=>document.getElementById(id);
 async function send(data){const r=await fetch('/api/stock_accounts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const j=await r.json();if(!r.ok||!j.ok)throw Error(j.error||'ตรวจบัญชีไม่สำเร็จ');return j;}
 function ready(message,verified){q('stockAccountStatus').textContent=message+(verified?' · เคยทดสอบดาวน์โหลดไฟล์จริงผ่านแล้ว':' · ยังไม่ได้ยืนยันการดาวน์โหลด กดทดสอบไฟล์จริงก่อนเริ่มตัด');q('stockPairingSection').hidden=true;q('stockPairingCode').value='';q('stockMainButton').textContent='เชื่อมแล้ว · ตรวจการเชื่อม';q('stockSetupSteps').hidden=true;}
 window.stockCopy=async function(id){try{const el=q(id);await navigator.clipboard.writeText(el.value||el.textContent);q('stockAccountStatus').textContent='คัดลอกแล้ว กลับไปวางใน Chrome ได้เลย';}catch(e){q('stockAccountStatus').textContent='คัดลอกไม่ได้ กรุณาเลือกข้อความแล้วคัดลอกด้วยตัวเอง';}};
 window.stockAccounts=async function(action){
  if(working)return;working=true;
  const section=q('stockAccountsPanel'),out=q('stockAccountStatus');section.querySelectorAll('button,select').forEach(e=>e.disabled=true);
  try{
   out.textContent='กำลังตรวจ…';const provider=q('stockAccountProvider').value;let j;
   if(action==='start'){try{j=await send({action:'check',provider});}catch(e){j=await send({action:'connect',provider,browser_mode:q('stockBrowserMode').value});}}
   else j=await send({action,browser_mode:action==='connect'?q('stockBrowserMode').value:undefined,path:action==='download_root'?q('stockDownloadRoot').value:undefined,kind:action==='test_download'?q('stockTestKind').value:undefined,provider});
   if(j.pairing_code){q('stockPairingSection').hidden=false;q('stockSetupSteps').hidden=false;q('stockPairingCode').value=j.pairing_code;q('stockExtensionFolder').textContent=j.extension_folder;out.textContent='เปิด Chrome แล้ว ทำตามขั้นตอน 1–3 ด้านล่าง หน้านี้จะตรวจการเชื่อมให้';}
   else if(j.job_id){const token=j.job_id;let finished=false;for(let i=0;i<480;i++){await new Promise(r=>setTimeout(r,1000));j=await send({action:'job_status',job_id:token});out.textContent=j.message;if(j.state==='done'){finished=true;break;}if(j.state==='failed')throw Error(j.message);}if(!finished){await send({action:'cancel',job_id:token});throw Error('หมดเวลาทดสอบ ยกเลิกงานแล้ว กรุณาตรวจ Chrome');}}
   else if(action==='check'||action==='start')ready(j.message,j.download_verified_at);
   else out.textContent=j.message;
   if(action==='disconnect'){q('stockPairingCode').value='';q('stockPairingSection').hidden=true;q('stockSetupSteps').hidden=false;q('stockMainButton').textContent='เชื่อมบัญชี / ตรวจการเชื่อม';}
  }catch(e){out.textContent=e.message;}finally{if(action==='test_download')q('stockTestResult').textContent='ผลทดสอบล่าสุด: '+out.textContent;working=false;section.querySelectorAll('button,select').forEach(e=>e.disabled=false);}
 };
 setInterval(async()=>{if(working||!q('stockAccountsPanel')?.open||document.hidden)return;working=true;try{const j=await send({action:'status'});const p=j.providers.find(p=>p.provider===q('stockAccountProvider').value);if(p?.state==='connected')ready(p.message,p.download_verified_at);else if(p?.state==='needs_login')q('stockAccountStatus').textContent=p.message;}catch(e){}finally{working=false;}},5000);
 q('stockAccountProvider')?.addEventListener('change',()=>{q('stockPairingCode').value='';q('stockPairingSection').hidden=true;q('stockSetupSteps').hidden=false;q('stockMainButton').textContent='เชื่อมบัญชี / ตรวจการเชื่อม';q('stockAccountStatus').textContent=q('stockAccountProvider').value==='envato'?'Envato ยังไม่รองรับดาวน์โหลดอัตโนมัติ':'ใช้บัญชี Artlist ของคุณ';});
})();
</script>
'''
