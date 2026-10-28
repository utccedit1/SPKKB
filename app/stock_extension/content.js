// Runs only on the catalog's public DOM. Never reads password fields, cookies or tokens.
async function stockPageTask(task){
 const sleep=ms=>new Promise(resolve=>{
  if(typeof MutationObserver==='undefined'){setTimeout(resolve,ms);return;}
  let timer;const observer=new MutationObserver(done);
  function done(){observer.disconnect();clearTimeout(timer);resolve();}
  observer.observe(document.documentElement||document.body,{subtree:true,childList:true});
  timer=setTimeout(done,ms);
 });
 function guard(){const text=document.body?.innerText||'';
  if(/verify you are human|checking your browser|complete the captcha/i.test(text)||[...document.querySelectorAll('iframe[src*="challenges.cloudflare.com"],iframe[src*="recaptcha"]')].some(e=>{const r=e.getBoundingClientRect();const s=getComputedStyle(e);const src=e.getAttribute('src')||'';const active=(src.includes('challenges.cloudflare.com')&&r.width>=200&&r.height>=50)||(src.includes('/bframe')&&r.width>=100&&r.height>=100);return active&&s.display!=='none'&&s.visibility!=='hidden';}))return 'captcha';
  if([...document.querySelectorAll('button,a')].some(b=>{const r=b.getBoundingClientRect?.();const s=getComputedStyle(b);return r&&r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&/^(Sign In|Log In)$/i.test((b.innerText||'').trim());}))return 'needs_login';return null;
 }
 if(task.action==='search_route'){
  const blocked=guard();if(blocked)return {error:blocked};
  if(typeof task.query!=='string'||!/^[-\w ,&()]{3,120}$/.test(task.query))return {error:'invalid_query'};
  const input=[...document.querySelectorAll('input')].find(e=>(e.getAttribute('role')==='combobox'||e.getAttribute('aria-label')==='Search')&&e.getClientRects().length);
  if(!input)return {error:'missing_search'};
  const submit=[...document.querySelectorAll('button')].find(b=>(b.getAttribute('aria-label')||b.innerText||'').trim()==='Search'&&!b.disabled&&b.getClientRects().length);
  if(!input.form&&!submit)return {error:'missing_search'};
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,task.query);
  input.dispatchEvent(new Event('input',{bubbles:true}));
  input.dispatchEvent(new Event('change',{bubbles:true}));
  await Promise.resolve();
  if(input.form)input.form.requestSubmit();else submit.click();
  return {navigated:true};
 }
 if(task.action==='open_clip'){
  const blocked=guard();if(blocked)return {error:blocked};
  let target;try{target=new URL(task.url);}catch{return {error:'invalid_url'};}
  if(target.origin!=='https://artlist.io'||!/^\/(stock-footage\/clip|royalty-free-music\/song)\//.test(target.pathname)||target.search||target.hash)return {error:'invalid_url'};
  const anchor=[...document.querySelectorAll('a[href]')].find(a=>a.href===target.href);
  if(!anchor)return {error:'missing_link'};
  anchor.click();return {navigated:true};
 }
 if(task.action==='status'){
  const blocked=guard();if(blocked)return {state:'needs_login',reason:blocked};
  const accountPaths=[...document.querySelectorAll('a[href]')].map(e=>{try{return new URL(e.href,location.href).pathname;}catch{return '';}});
  const catalogAccount=accountPaths.some(p=>/^\/downloads(?:\/|$)/.test(p))&&accountPaths.some(p=>/^\/favorites(?:\/|$)/.test(p));
  const positive=catalogAccount||[...document.querySelectorAll('a,button')].some(e=>{
   const label=(e.getAttribute('aria-label')||'')+' '+(e.innerText||'');
   if(/my account|my downloads|log out|sign out|account menu|user menu|profile/i.test(label))return true;
   const r=e.getBoundingClientRect?.(),s=getComputedStyle(e);
   return r&&r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&/^Get More AI Credits$/i.test((e.innerText||'').trim());
  });
  return {state:positive?'connected':'needs_login',reason:positive?'':'account_not_found',signals:{links:accountPaths.length,downloads:accountPaths.some(p=>/^\/downloads(?:\/|$)/.test(p)),favorites:accountPaths.some(p=>/^\/favorites(?:\/|$)/.test(p)),controls:document.querySelectorAll('a,button').length}};
 }
 let openedDownload=false;let formatCount=0,primaryCount=0,catalogReadyAt=0,catalogSignature='';
 // Background tabs throttle timers; bound elapsed time rather than 40 delayed ticks.
 const deadline=Date.now()+20000;
 while(Date.now()<deadline){const err=guard();if(err)return {error:err};
  if(task.action==='search'){
   const prefix=task.kind==='broll'?'/stock-footage/clip/':'/royalty-free-music/song/';
   const ignored=new Set(['stock','footage','video','vertical','portrait','with','and','the']);
   const groups=[['documents','document','papers','paper','paperwork'],['reviewing','review','reviews','reading','read','checking','check','handling','sorting'],['stacked','stack','stacks','pile','piles'],['desk','table','desktop'],['person','people','man','woman','worker','employee'],['calendar','calendars'],['grocery','groceries','supermarket','supermarkets'],['checkout','cashier','cashiers'],['coupon','coupons','voucher','vouchers'],['sticker','stickers','label','labels'],['product','products','item','items'],['stamp','stamps','stamping'],['dates','date'],['flipping','flip','turning','turn'],['page','pages']];
   const canonical=w=>groups.find(g=>g.includes(w))?.[0]||w;
   const terms=new Set((task.query.toLowerCase().match(/[a-z]{3,}/g)||[]).filter(w=>!ignored.has(w)).map(canonical));let best=null;
   const required=Array.isArray(task.required_terms)?task.required_terms.map(w=>canonical(String(w).toLowerCase())):[];
   for(const a of document.querySelectorAll('a[href]')){
    const url=new URL(a.href,location.href);if((task.exclude_urls||[]).includes(url.href))continue;if(url.origin!=='https://artlist.io'||!url.pathname.startsWith(prefix)||url.search||url.hash)continue;
    const label=[a.innerText,a.querySelector('img')?.alt,a.getAttribute('aria-label')].map(v=>String(v||'').trim()).find(Boolean);
    const title=label||decodeURIComponent(url.pathname.split('/').filter(Boolean).slice(-2).join(' ')).replaceAll('-',' ').trim();
    let matchText=title;
    if(task.kind==='music'){
     // Song titles rarely contain mood/genre terms. Read only this song's
     // bounded result row, never the surrounding list of unrelated tracks.
     let row=a.parentElement;
     for(let depth=0;row&&depth<5;depth++,row=row.parentElement){
      const songs=[...row.querySelectorAll('a[href]')].filter(link=>{try{return new URL(link.href,location.href).pathname.startsWith('/royalty-free-music/song/');}catch{return false;}});
      if(songs.length>1)break;
      if(songs.length===1&&row.querySelector('button[aria-label="download"]')){matchText+=' '+(row.innerText||'');break;}
     }
    }
    const words=new Set((matchText.toLowerCase().match(/[a-z]{3,}/g)||[]).map(canonical));
    const hits=[...terms].filter(w=>words.has(w)).length;
    // Two explicit essential concepts (e.g. reviewing + documents) are stronger
    // than optional setting words such as person/desk/checklist.
    const essentialMatch=new Set(required).size>=2&&required.every(w=>words.has(w));
    if(task.kind==='broll'&&(required.some(w=>!words.has(w))||hits<Math.min(2,terms.size)||(!essentialMatch&&hits/Math.max(1,terms.size)<.5)))continue;
    if((task.kind==='music'?hits>0:hits>0)&&(!best||hits>best.score))best={url:url.href,title,score:hits};
   }
   if(best)return best;
   const signature=[...document.querySelectorAll('a[href]')].filter(a=>{try{return new URL(a.href,location.href).pathname.startsWith(prefix);}catch{return false;}}).slice(0,40).map(a=>a.href).join('|');
   if(signature){if(signature!==catalogSignature){catalogSignature=signature;catalogReadyAt=Date.now();}else if(Date.now()-catalogReadyAt>=2500)return {error:'no_match'};}

  }else if(task.action==='download'){
   if(/download preview|watermarked preview/i.test(document.body.innerText))return {error:'preview'};
   {
    const format=task.kind==='broll'?'HD':'MP3';
    const hd=[...document.querySelectorAll('button')].filter(b=>[b.innerText,b.getAttribute('aria-label'),b.getAttribute('title')].some(label=>{const text=String(label||'').normalize('NFKC').replace(/\p{Cf}/gu,'').trim();return text===format||(format==='MP3'&&text.length<80&&/\bMP3\b/i.test(text)&&!/\bWAV\b/i.test(text));})&&b.getClientRects().length&&!b.disabled);
    formatCount=hd.length;let formats=hd;
    if(hd.length>1&&task.kind==='music'){
     let scope=document.querySelector('h1')?.parentElement;
     for(let depth=0;scope&&depth<5;depth++,scope=scope.parentElement){const local=hd.filter(b=>scope.contains(b));if(local.length){formats=local;break;}}
    }
    if(formats.length===1){formats[0].click();return {clicked:true};}
    if(openedDownload){await sleep(500);continue;}
   }
   const names=task.kind==='broll'?/^(download-clip|Download)$/:/^(download-song|direct download|download)$/i;
   let buttons=[...document.querySelectorAll('button')].filter(b=>names.test((b.getAttribute('aria-label')||b.getAttribute('title')||b.innerText||'').trim())&&b.getClientRects().length&&!b.disabled);
   if(task.kind==='music'){const primary=buttons.filter(b=>/^(download-song|direct download)$/i.test((b.getAttribute('aria-label')||b.getAttribute('title')||b.innerText||'').trim()));if(primary.length===1)buttons=primary;}
   // Artlist replaces a previously downloaded clip's named button with an
   // unlabeled checkmark. Accept only the icon immediately before its favorite
   // button in the same small action group; never a related SFX/player control.
   if(!buttons.length&&task.kind==='broll'&&/^\/stock-footage\/clip\//.test(location.pathname)&&document.querySelector('h1')){
    const favorites=[...document.querySelectorAll('button')].filter(b=>b.getAttribute('aria-label')==='Add to favorites'&&b.getClientRects().length);
    for(const favorite of favorites){
     let group=favorite.parentElement;
     for(let depth=0;group&&depth<3;depth++,group=group.parentElement){
      const controls=[...group.querySelectorAll('button')];
      if(controls.length<2)continue;
      const candidate=controls[0];
      if(controls.length<=5&&controls[1]===favorite&&!candidate.disabled&&candidate.getClientRects().length&&!(candidate.getAttribute('aria-label')||candidate.getAttribute('title')||candidate.innerText||'').trim()&&candidate.querySelector('svg'))buttons.push(candidate);
      break;
     }
    }
   }
   primaryCount=buttons.length;
   if(buttons.length===1){buttons[0].click();openedDownload=true;}
  }
  await sleep(500);
 }
 if(task.action==='search'){
  const links=[...document.querySelectorAll('a[href]')].some(a=>/\/(stock-footage\/clip|royalty-free-music\/song)\//.test(a.href||''));
  const empty=/no results|no footage found|couldn.t find any|nothing found/i.test(document.body?.innerText||'');
  return {error:links||empty?'no_match':'page_not_ready'};
 }
 // Reload is safe only before any download control has been clicked.
 if(!openedDownload&&document.querySelectorAll('button,a').length<5)return {error:'page_not_ready'};
 return {error:'download_controls',control_debug:{formats:formatCount,primary:primaryCount,opened:Number(openedDownload)}};
}
