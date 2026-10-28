const fs=require('fs'),vm=require('vm'),assert=require('assert');
(async()=>{
 const source=fs.readFileSync('app/ks/editor_page.html','utf8');
 const watch=source.slice(source.indexOf('async function watchReseg(){'),source.indexOf('async function aiReseg(){'));
 const elements=new Map();const el=id=>{if(!elements.has(id))elements.set(id,{textContent:'',disabled:false});return elements.get(id)};
 const store=new Map([['fixture-key','gone']]);let requests=0;
 const c=vm.createContext({$:el,window:{},location:{search:'?workspace=fixture',pathname:'/editor'},URLSearchParams,sessionStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},fetch:async()=>{requests++;return {ok:true,json:async()=>({ok:false,code:'job_not_found',error:'fixture missing job'})}},setTimeout,console,Map});
 vm.runInContext("const resegStorageKey='fixture-key';var resegBusy=false,resegJob='gone';function resegControls(){};function msg(){};async function ensureCapsLatest(){};",c);
 vm.runInContext(watch,c);await vm.runInContext('watchReseg()',c);
 const stuck=vm.runInContext("resegJob==='gone'&&!resegBusy",c)&&store.has('resegJob')&&requests===1;
 assert.equal(vm.runInContext('resegJob',c),null);
 assert.equal(vm.runInContext('resegBusy',c),false);assert(!store.has('fixture-key'));
 vm.runInContext("resegJob='offline-job'",c);store.set('fixture-key','offline-job');
 c.fetch=async()=>{throw Error('offline')};await vm.runInContext('watchReseg()',c);
 assert.equal(vm.runInContext('resegJob',c),'offline-job');assert.equal(store.get('fixture-key'),'offline-job');
 assert(source.includes("'resegJob:'+new URLSearchParams(location.search).get('workspace')"));
 // Show that there is no immediate next-job poll after download completion.
 const worker=fs.readFileSync('app/stock_extension/worker.js','utf8');let changed,alarms=[],pollPosts=0;
 let active={id:'fixture',downloadId:7,url:'https://artlist.io/stock-footage/clip/fixture',title:'Fixture'};
 const event={addListener(){}};
 const chrome={storage:{local:{get:async key=>key==='activeJob'?{activeJob:active}:{},remove:async()=>{active=null}}},runtime:{onMessage:event},downloads:{onDeterminingFilename:event,onChanged:{addListener:fn=>changed=fn},search:async()=>[{filename:'/tmp/fixture.mp4'}]},alarms:{get:async()=>null,create:async(n,v)=>alarms.push(v),onAlarm:event},tabs:{onUpdated:event}};
 const scheduled=[];const w=vm.createContext({chrome,URL,AbortSignal,setTimeout:fn=>{scheduled.push(fn);return scheduled.length},clearTimeout:()=>{},console});vm.runInContext(worker,w);vm.runInContext("post=async d=>({ok:true});phase=async()=>{};poll=async()=>{pollPosts++};var pollPosts=0;",w);
 await changed({id:7,state:{current:'complete'}});await Promise.resolve();
 const noWake=vm.runInContext('pollPosts',w)===0&&active===null;
 assert.equal(scheduled.length,1);await scheduled[0]();assert.equal(vm.runInContext('pollPosts',w),1);assert(alarms.some(x=>x.periodInMinutes===.5));
 console.log('Readiness: missing job clears receipt; download completion wakes next queue within 2 seconds');
})().catch(e=>{console.error(e);process.exit(1)});
