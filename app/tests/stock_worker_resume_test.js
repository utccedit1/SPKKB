const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const event={addListener(){}};
let store={},ticks=0,cleared=0,heartbeats=0,phases=[];
const chrome={storage:{local:{get:async key=>typeof key==='string'?{[key]:store[key]}:store,set:async v=>Object.assign(store,v),remove:async k=>delete store[k]}},runtime:{onMessage:event},downloads:{onDeterminingFilename:event,onChanged:event},alarms:{get:async()=>true,onAlarm:event},tabs:{onUpdated:event,get:async()=>({})}};
const c=vm.createContext({chrome,URL,AbortSignal,setTimeout:()=>1,clearTimeout:()=>{},setInterval:fn=>{c.tick=fn;ticks++;return 1},clearInterval:()=>cleared++});
vm.runInContext(fs.readFileSync('app/stock_extension/worker.js','utf8'),c);
vm.runInContext("post=async data=>{if(data.action==='heartbeat')heartbeatCount++;return {state:'running'}};var heartbeatCount=0;phase=async()=>{};chooseStock=async()=>{await tick();return {error:'no_match'}};fail=async()=>{}",c);
(async()=>{
 await vm.runInContext("run({id:'a',kind:'broll',query:'calendar',download_folder:'ChuayDaiStock/aaaaaaaaaaaaaaaa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'},1)",c);
 assert.equal(store.activeJob.phase,'searching');assert.equal(ticks,1);assert.equal(cleared,1);assert.equal(vm.runInContext('heartbeatCount',c),1);
 store={connection:{},activeJob:{id:'b',created:Date.now(),phase:'searching',tabId:1}};
 vm.runInContext("var resumed=0;run=async()=>{resumed++}",c);await vm.runInContext('poll()',c);assert.equal(vm.runInContext('resumed',c),1);
 store.activeJob.downloadRequested=true;store.activeJob.phase='download_requested';await vm.runInContext('poll()',c);assert.equal(vm.runInContext('resumed',c),1);
 console.log('Worker: saves searching job, scoped heartbeat, resumes search after restart, never repeats an attempted download');
})().catch(e=>{console.error(e);process.exitCode=1});
