const out=document.getElementById('status');
document.getElementById('pair').onclick=async()=>{
 try{const raw=document.getElementById('code').value.trim();const cfg=JSON.parse(atob(raw.replace(/-/g,'+').replace(/_/g,'/')));const u=new URL(cfg.base);
 if(u.protocol!=='http:'||u.hostname!=='127.0.0.1'||!/^\d+$/.test(u.port)||u.username||u.password||u.pathname!=='/'||u.search||u.hash||!['artlist','envato'].includes(cfg.provider)||!/^[-\w]{40,64}$/.test(cfg.token))throw Error('รหัสเชื่อมไม่ถูกต้อง');
 await chrome.storage.local.set({connection:cfg});const tab=await chrome.tabs.create({active:false,url:cfg.provider==='artlist'?'https://artlist.io/stock-footage':'https://app.envato.com/stock-video'});await chrome.storage.local.set({stockTab:tab.id});document.getElementById('code').value='';await chrome.runtime.sendMessage({action:'poll'});out.textContent='เชื่อมแล้ว ล็อกอินบนเว็บของคุณ แอปจะตรวจสถานะให้อัตโนมัติ';await chrome.tabs.update(tab.id,{active:true});
 }catch(e){out.textContent='เชื่อมไม่สำเร็จ ตรวจรหัสและเปิดแอปช่วยด้วยจ้าก่อน';}
};
document.getElementById('check').onclick=async()=>{const r=await chrome.runtime.sendMessage({action:'poll'});out.textContent=r?.message||'ส่งสถานะแล้ว กลับไปตรวจในแอป';};
document.getElementById('forget').onclick=async()=>{await chrome.storage.local.remove(['connection','stockTab','activeJob']);out.textContent='ลืมการเชื่อมแล้ว';};
