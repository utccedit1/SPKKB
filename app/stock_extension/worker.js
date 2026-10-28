let polling=false,pollTimer=null;
function wakeQueue(){if(pollTimer!==null)clearTimeout(pollTimer);pollTimer=setTimeout(()=>{pollTimer=null;poll();},2000);}
async function config(){return (await chrome.storage.local.get('connection')).connection;}
async function post(data){const c=await config();if(!c)throw Error('not paired');const r=await fetch(c.base+'/api/stock_bridge',{method:'POST',headers:{'Content-Type':'application/json','X-Stock-Extension-Origin':chrome.runtime.getURL('').replace(/\/$/,''),'Authorization':'Bearer '+c.token},body:JSON.stringify(data),signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('bridge_http_'+r.status);return r.json();}
async function pageTask(tabId,task){await chrome.scripting.executeScript({target:{tabId},files:['content.js']});const results=await chrome.scripting.executeScript({target:{tabId},func:async data=>stockPageTask(data),args:[task]});return results[0]?.result||{error:'download_failed'};}
function samePage(actual,expected){try{const a=new URL(actual),e=new URL(expected);return a.origin===e.origin&&a.pathname.replace(/\/$/,'')===e.pathname.replace(/\/$/,'')&&(e.searchParams.has('terms')?a.searchParams.get('terms')===e.searchParams.get('terms'):a.search===e.search);}catch{return false;}}
async function ready(tabId,expected){for(let i=0;i<60;i++){const t=await chrome.tabs.get(tabId);if(t.status==='complete'&&samePage(t.url,expected))return;await new Promise(r=>setTimeout(r,500));}throw Error('page');}
async function phase(job,stage,extra={}){try{await post({action:'progress',job_id:job.id,stage,...extra});}catch(e){}}
async function chooseStock(job,tabId){
 await chrome.tabs.update(tabId,{active:true});
 const base=job.kind==='broll'?'https://artlist.io/stock-footage/search':'https://artlist.io/royalty-free-music/search';
 async function search(query){
  const url=base+'?terms='+encodeURIComponent(query);
  for(let attempt=0;attempt<3;attempt++){
   await phase(job,'search',{attempt:attempt+1});
   if(attempt===0){
    const current=await chrome.tabs.get(tabId);
    if(!samePage(current.url,url)){
     const catalog=job.kind==='broll'?'/stock-footage':'/royalty-free-music';
     // The site's shared search box searches the current catalog. Never submit
     // a music brief from a footage page (or the reverse).
     if(!new URL(current.url).pathname.startsWith(catalog+'/')&&new URL(current.url).pathname!==catalog){
      await chrome.tabs.update(tabId,{url,active:true});
     }else{
      const routed=await pageTask(tabId,{action:'search_route',kind:job.kind,query});
      if(routed.error==='captcha'||routed.error==='needs_login')return routed;
      if(routed.navigated!==true)await chrome.tabs.update(tabId,{url,active:true});
     }
    }
   }
   // Allow one full recovery only before selection/download, after a failed hydration check.
   if(attempt===1){const current=await chrome.tabs.get(tabId);if(samePage(current.url,url))await chrome.tabs.reload(tabId);}
   await ready(tabId,url);
   const result=await pageTask(tabId,{action:'search',kind:job.kind,query,required_terms:job.required_terms||[],exclude_urls:job.exclude_urls||[]});
   // Never retry login or human verification. Only retry an unhydrated catalog.
   if(result.error!=='page_not_ready'||attempt===2)return result;
   await new Promise(r=>setTimeout(r,2000*(attempt+1)));
  }
 }
 let selected=await search(job.query);
 const essentials=[...new Set((job.required_terms||[]).filter(w=>typeof w==='string'&&/^[a-z]{3,30}$/i.test(w)).map(w=>w.toLowerCase()))];
 const focused=essentials.join(' ');
 // One bounded retry removes optional setting words, never the required concepts.
 if(selected.error==='no_match'&&job.kind==='broll'&&essentials.length>=2&&focused!==job.query.toLowerCase())selected=await search(focused);
 return selected;
}
async function downloadStock(job,tabId,url){
 for(let attempt=0;attempt<3;attempt++){
  await phase(job,'selected',{attempt:attempt+1});
  if(attempt)await ready(tabId,url);
  const result=await pageTask(tabId,{action:'download',kind:job.kind});
  if(result.error!=='page_not_ready'||attempt===2)return result;
  await new Promise(r=>setTimeout(r,2000*(attempt+1)));
 }
}
async function fail(job,error,details={}){try{await post({...details,action:'result',job_id:job.id,error});}finally{const {activeJob}=await chrome.storage.local.get('activeJob');if(activeJob?.id===job.id)await chrome.storage.local.remove('activeJob');}}
async function run(job,tabId){
 // Scope the keep-alive to this job; an idle extension is still allowed to sleep.
 const heartbeat=setInterval(()=>{chrome.storage.local.get('activeJob').then(({activeJob})=>{if(activeJob?.id===job.id)return post({action:'heartbeat',job_id:job.id});}).catch(()=>{});},15000);
 let step='search';
 try{
  await chrome.storage.local.set({activeJob:{...job,tabId,phase:'searching',created:job.created||Date.now()}});
  if(!['broll','music'].includes(job.kind)||!/^[-\w ,&()]{3,120}$/.test(job.query)||!/^ChuayDaiStock\/[a-f0-9]{16}\/[a-f0-9]{32}$/.test(job.download_folder))return fail(job,'download_failed');
  // Verified stock-footage search route. Music uses the site's shared catalog search route.
  const selected=await chooseStock(job,tabId);if(selected.error)return fail(job,selected.error);
  const u=new URL(selected.url);const prefix=job.kind==='broll'?'/stock-footage/clip/':'/royalty-free-music/song/';if(u.origin!=='https://artlist.io'||!u.pathname.startsWith(prefix)||u.search)return fail(job,'no_match');
  await chrome.storage.local.set({activeJob:{...job,...selected,tabId,phase:'opening',created:job.created||Date.now()}});
  step='download';await phase(job,'selected');
  // Use the site's own route handler; hard navigation discards the hydrated catalog.
  const opened=await pageTask(tabId,{action:'open_clip',url:selected.url});
  if(opened.error==='captcha'||opened.error==='needs_login')return fail(job,opened.error);
  if(opened.navigated!==true)await chrome.tabs.update(tabId,{url:selected.url,active:true});
  await ready(tabId,selected.url);
  await chrome.tabs.update(tabId,{active:true});
  await chrome.storage.local.set({activeJob:{...job,...selected,tabId,phase:'download_requested',downloadRequested:true,created:job.created||Date.now()}});
  const clicked=await downloadStock(job,tabId,selected.url);if(clicked.error)return fail(job,clicked.error,{control_debug:clicked.control_debug});
  await phase(job,'download');
 }catch(e){await fail(job,step==='search'?'search_failed':'download_failed').catch(()=>{});}finally{clearInterval(heartbeat);}
}
async function poll(){
 if(polling)return {message:'กำลังตรวจอยู่'};polling=true;let stage='config';
 try{const c=await config();if(!c)return {message:'วางรหัสเชื่อมก่อน'};
  const state=await chrome.storage.local.get(['stockTab','activeJob']);if(state.activeJob){if(Date.now()-state.activeJob.created>480000){await fail(state.activeJob,'download_failed');return {message:'งานเดิมหมดเวลาแล้ว'};}const current=await post({action:'job_status',job_id:state.activeJob.id});if(['missing','failed','done'].includes(current.state)){await chrome.storage.local.remove('activeJob');return {message:'งานเดิมจบแล้ว พร้อมเริ่มงานใหม่'};}if(!state.activeJob.downloadRequested&&['searching','opening'].includes(state.activeJob.phase)){await run(state.activeJob,state.activeJob.tabId);return {message:'กู้คืนงานค้นหาหลังส่วนขยายพักแล้ว'};}if(state.activeJob.downloadId){const [item]=await chrome.downloads.search({id:state.activeJob.downloadId});if(item)await phase(state.activeJob,'download',{received:item.bytesReceived,total:item.totalBytes});}return {message:state.activeJob.downloadId?'กำลังรับไฟล์ดาวน์โหลด':'กดดาวน์โหลดแล้ว แต่ Chrome ยังไม่เริ่มรับไฟล์ กรุณาตรวจหน้าต่าง Artlist'};}
  let tab=Number.isInteger(state.stockTab)?await chrome.tabs.get(state.stockTab).catch(()=>null):null;
  if(!tab||!/^https:\/\/artlist\.io(?:\/|$)/.test(tab.url||'')){const existing=await chrome.tabs.query({url:'https://artlist.io/*'});tab=existing[0]||await chrome.tabs.create({url:'https://artlist.io/stock-footage',active:false});await chrome.storage.local.set({stockTab:tab.id});}
  let account='needs_login',reason='',signals=null;
  stage='page';if(tab&&/^https:\/\/artlist\.io(?:\/|$)/.test(tab.url||'')){const checked=await pageTask(tab.id,{action:'status'});account=checked.state;reason=checked.reason||'';signals=checked.signals;}
  // An inactive search page may not have hydrated its account navigation yet.
  // Check another already-open Artlist page without moving the user's tabs.
  if(reason==='account_not_found'){
   const alternatives=await chrome.tabs.query({url:'https://artlist.io/*'});
   for(const other of alternatives.filter(t=>t.id!==tab?.id&&t.status==='complete').slice(0,4)){
    const checked=await pageTask(other.id,{action:'status'}).catch(()=>null);
    if(checked?.state==='connected'){account='connected';reason='';break;}
   }
  }
  stage='bridge';const result=await post({action:'poll',account_state:account,account_reason:reason});if(result.job&&tab)await run(result.job,tab.id);
  return {message:account==='connected'?'ตรวจพบบัญชีแล้ว':reason==='captcha'?'Artlist ขอให้ยืนยัน CAPTCHA บนเว็บ':reason==='needs_login'?'พบปุ่มเข้าสู่ระบบบนเว็บ':reason==='account_not_found'?'ยังไม่พบเมนูบัญชีในหน้าเว็บนี้ ลองเปิดหน้า Artlist หลักแล้วตรวจอีกครั้ง'+(signals?' (ลิงก์ '+signals.links+', ปุ่ม/ลิงก์ '+signals.controls+', Downloads '+Number(signals.downloads)+', Favorites '+Number(signals.favorites)+')':''):'กำลังรอหน้า Artlist พร้อมใช้งาน'};
 }catch(e){const reason=/^bridge_http_\d{3}$/.test(e.message)?e.message:(e.name==='TypeError'?'network':e.message?.includes('stockPageTask')?'page_script':'browser_page');return {message:'เชื่อมแอปไม่ได้ ('+stage+':'+reason+') เปิดช่วยด้วยจ้าและตรวจรหัสเชื่อมอีกครั้ง'};}finally{polling=false;if(await config().catch(()=>null))wakeQueue();}
}
chrome.downloads.onDeterminingFilename.addListener((item,suggest)=>{
 chrome.storage.local.get('activeJob').then(({activeJob:j})=>{if(j&&j.downloadRequested===true&&Date.now()-j.created<480000&&new URL(item.url).protocol==='https:'&&/^https:\/\/artlist\.io\//.test(item.referrer||'')){
  const name=item.filename.split(/[\\/]/).pop().replace(/[^\w.\-]/g,'_');chrome.storage.local.set({activeJob:{...j,downloadId:item.id}}).then(()=>suggest({filename:j.download_folder+'/'+name,conflictAction:'uniquify'}));
 }else suggest();}).catch(()=>suggest());return true;
});
chrome.downloads.onChanged.addListener(async delta=>{
 if(delta.state?.current!=='complete'&&delta.state?.current!=='interrupted')return;
 const {activeJob:j}=await chrome.storage.local.get('activeJob');if(!j||j.downloadId!==delta.id)return;
 try{if(delta.state.current==='interrupted')return await fail(j,'download_failed');
  await phase(j,'verify');
  const [item]=await chrome.downloads.search({id:delta.id});await post({action:'result',job_id:j.id,filename:item.filename,url:j.url,title:j.title});await chrome.storage.local.remove('activeJob');
 }catch(e){await fail(j,'download_failed').catch(()=>{});}finally{wakeQueue();}
});
chrome.runtime.onMessage.addListener((message,sender,reply)=>{if(message.action==='poll'){poll().then(reply);return true;}});
async function ensureAlarm(){if(!await chrome.alarms.get('stock-poll'))await chrome.alarms.create('stock-poll',{periodInMinutes:.5});}
ensureAlarm().catch(()=>{});chrome.alarms.onAlarm.addListener(a=>{if(a.name==='stock-poll')poll();});
chrome.tabs.onUpdated.addListener((id,info)=>{if(info.status==='complete')poll();});
