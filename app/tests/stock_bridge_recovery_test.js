const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
(async()=>{
 const source=fs.readFileSync(path.join(__dirname,'../stock_extension/content.js'),'utf8');
 for(const visible of [false,true]){
  const iframe={getAttribute:()=> 'https://www.google.com/recaptcha/api2/bframe',getBoundingClientRect:()=>({width:visible?300:0,height:visible?220:0})};
  const context=vm.createContext({setTimeout,URL,location:{href:'https://artlist.io/stock-footage/search'},document:{body:{innerText:'Your account'},querySelectorAll:s=>s.includes('iframe')?[iframe]:s==='a[href]'?[{href:'https://artlist.io/downloads'},{href:'https://artlist.io/favorites'}]:[],querySelector:s=>s.includes('/downloads/')||s.includes('/favorites/')?{}:null},getComputedStyle:()=>({display:visible?'block':'none',visibility:visible?'visible':'hidden'})});
  vm.runInContext(source,context);
  const result=await vm.runInContext("stockPageTask({action:'status'})",context);
  assert.equal(result.state,visible?'needs_login':'connected');
 }
 for(const visible of [false,true]){
  const signIn={innerText:'Sign In',getBoundingClientRect:()=>({width:visible?90:0,height:visible?30:0})};
  const badge={getAttribute:()=> 'https://www.google.com/recaptcha/api2/anchor',getBoundingClientRect:()=>({width:256,height:60})};
  const context=vm.createContext({setTimeout,URL,location:{href:'https://artlist.io/stock-footage/search'},document:{body:{innerText:'Your account'},querySelectorAll:s=>s.includes('iframe')?[badge]:s==='a[href]'?[{href:'https://artlist.io/downloads/'},{href:'https://artlist.io/favorites/music'}]:[signIn],querySelector:()=>({})},getComputedStyle:()=>({display:'block',visibility:'visible'})});
  vm.runInContext(source,context);
  const result=await vm.runInContext("stockPageTask({action:'status'})",context);
  assert.equal(result.state,visible?'needs_login':'connected');
  assert.notEqual(result.reason,'captcha');
 }
 {
  const link={href:'https://artlist.io/stock-footage/clip/students-portrait-talking-campus/6308332',innerText:'  \n ',querySelector:()=>null,getAttribute:()=>null};
  const context=vm.createContext({setTimeout:fn=>{fn();return 0;},URL,location:{href:'https://artlist.io/stock-footage/search?terms=university%20students%20campus'},document:{body:{innerText:'Your account'},querySelectorAll:s=>s==='a[href]'?[link]:[]},getComputedStyle:()=>({display:'block',visibility:'visible'})});
  vm.runInContext(source,context);
  const result=await vm.runInContext("stockPageTask({action:'search',kind:'broll',query:'university students campus'})",context);
  assert.equal(result.url,link.href);assert.match(result.title,/students portrait/);
  link.href='https://artlist.io/stock-footage/clip/deciding-reviewing-sketch-papers/6271998';
  const essential=await vm.runInContext("stockPageTask({action:'search',kind:'broll',query:'person reviewing documents checklist desk',required_terms:['reviewing','documents']})",context);
  assert.equal(essential.url,link.href);
  const unrelated=await vm.runInContext("stockPageTask({action:'search',kind:'broll',query:'calendar flipping',required_terms:['calendar','flipping']})",context);
  assert.equal(unrelated.error,'no_match');
 }
 for(const visible of [false,true]){
  const credit={innerText:'Get More AI Credits',getAttribute:()=>'',getBoundingClientRect:()=>({width:visible?200:0,height:visible?40:0})};
  const context=vm.createContext({setTimeout,URL,location:{href:'https://artlist.io/stock-footage/search'},document:{body:{innerText:'Get More AI Credits'},querySelectorAll:s=>s==='a,button'||s==='button,a'?[credit]:[]},getComputedStyle:()=>({display:'block',visibility:'visible'})});
  vm.runInContext(source,context);const result=await vm.runInContext("stockPageTask({action:'status'})",context);
  assert.equal(result.state,visible?'connected':'needs_login');
 }
 const worker=fs.readFileSync(path.join(__dirname,'../stock_extension/worker.js'),'utf8');
 let store={connection:{base:'http://127.0.0.1:8765',token:'fixture'},activeJob:{id:'old',created:0}};
 let response='forbidden';
 const event={addListener:()=>{}};
 const chrome={storage:{local:{get:async keys=>typeof keys==='string'?{[keys]:store[keys]}:Object.fromEntries(keys.map(k=>[k,store[k]])),remove:async key=>{delete store[key];},set:async values=>Object.assign(store,values)}},runtime:{getURL:()=> 'chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/',onMessage:event},downloads:{onDeterminingFilename:event,onChanged:event},alarms:{get:async()=>null,create:()=>{},onAlarm:event},tabs:{onUpdated:event}};
 const context=vm.createContext({chrome,URL,AbortSignal,Date,setTimeout,fetch:async()=>({ok:response!=='forbidden',status:403,json:async()=>({state:'missing'})})});
 vm.runInContext(worker,context);
 await vm.runInContext("fail({id:'old'},'download_failed').catch(()=>{})",context);
 assert.equal(store.activeJob,undefined);
 store.activeJob={id:'new',created:Date.now()};
 await vm.runInContext("fail({id:'old'},'download_failed').catch(()=>{})",context);
 assert.equal(store.activeJob.id,'new');
 response='missing';
 await vm.runInContext('poll()',context);
 assert.equal(store.activeJob,undefined);
 chrome.tabs.update=async()=>{};chrome.tabs.get=async()=>({url:"https://artlist.io/stock-footage"});
 vm.runInContext("ready=async()=>{};var searchQueries=[];pageTask=async(id,task)=>{if(task.action==='search_route')return {error:'missing_search'};searchQueries.push(task.query);return searchQueries.length===1?{error:'no_match'}:{url:'https://artlist.io/stock-footage/clip/reviewing-documents/123'};}",context);
 const chosen=await vm.runInContext("chooseStock({kind:'broll',query:'person reviewing curriculum documents desk',required_terms:['reviewing','documents']},1)",context);
 assert.match(chosen.url,/reviewing-documents/);assert.equal(JSON.stringify(vm.runInContext('searchQueries',context)),JSON.stringify(['person reviewing curriculum documents desk','reviewing documents']));
 vm.runInContext("searchQueries=[];pageTask=async(id,task)=>{if(task.action==='search_route')return {error:'missing_search'};searchQueries.push(task.query);return {error:'captcha'};}",context);
 await vm.runInContext("chooseStock({kind:'broll',query:'person reviewing curriculum documents desk',required_terms:['reviewing','documents']},1)",context);
 assert.equal(vm.runInContext('searchQueries.length',context),1);
 let created=0;chrome.alarms.get=async()=>({name:'stock-poll'});chrome.alarms.create=async()=>{created++;};
 await vm.runInContext('ensureAlarm()',context);assert.equal(created,0);
 chrome.alarms.get=async()=>null;await vm.runInContext('ensureAlarm()',context);assert.equal(created,1);
 console.log('Stock bridge: visible account signals, hidden/active CAPTCHA, whitespace titles, required concepts, bounded search retry, no CAPTCHA retry, persistent alarm, failed report cleanup and owner job reconciliation passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
