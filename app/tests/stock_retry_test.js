const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const event={addListener(){}};
async function scenario(results){
 let calls=0,reloads=0,searches=0;
 const chrome={storage:{local:{get:async()=>({}),set:async()=>{}}},runtime:{onMessage:event},downloads:{onDeterminingFilename:event,onChanged:event},alarms:{get:async()=>true,onAlarm:event},tabs:{onUpdated:event,update:async()=>{searches++;},reload:async()=>{reloads++;},get:async()=>({status:'complete',url:'https://artlist.io/stock-footage/search?terms=calendar'})}};
 const context=vm.createContext({chrome,URL,AbortSignal,setTimeout:fn=>fn()});
 vm.runInContext(fs.readFileSync('app/stock_extension/worker.js','utf8'),context);
 context.reply=()=>{calls++;return results[Math.min(calls-1,results.length-1)];};
 vm.runInContext('phase=async()=>{};pageTask=async()=>reply()',context);
 assert.equal(vm.runInContext("samePage('https://artlist.io/stock-footage/search?terms=calendar+dates','https://artlist.io/stock-footage/search?terms=calendar%20dates')",context),true);
 const result=await vm.runInContext("chooseStock({id:'test',kind:'broll',query:'calendar',required_terms:['calendar']},1)",context);
 const download=async()=>vm.runInContext("downloadStock({id:'test',kind:'broll'},1,'https://artlist.io/stock-footage/search?terms=calendar')",context);
 return {result,calls,reloads,searches,download};
}
(async()=>{
 let s=await scenario([{error:'page_not_ready'},{url:'https://artlist.io/stock-footage/clip/calendar/1'}]);assert.equal(s.reloads,1);assert(s.result.url);
 s=await scenario([{error:'page_not_ready'}]);assert.equal(s.calls,3);assert.equal(s.reloads,1);assert.equal(s.result.error,'page_not_ready');
 for(const error of ['captcha','needs_login','no_match']){s=await scenario([{error}]);assert.equal(s.calls,1);assert.equal(s.reloads,0);}
 let downloaded=await scenario([{clicked:true}]);assert.equal((await downloaded.download()).clicked,true);
 let control=await scenario([{error:'download_controls'}]);assert.equal((await control.download()).error,'download_controls');
 console.log('Stock retry: recovers page readiness, caps retries, never retries CAPTCHA/login/no-match');
})().catch(e=>{console.error(e);process.exitCode=1;});
