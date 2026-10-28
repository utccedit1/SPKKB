const fs=require('fs'),vm=require('vm'),assert=require('assert');
const raw=fs.readFileSync('app/ks/studio_workflow.py','utf8').split("JS=r'''")[1].split("'''")[0];
const code=raw.slice(raw.indexOf('let AC_PLAN_META'),raw.indexOf(" document.addEventListener('DOMContentLoaded'"))+'})();';
function page(workspace,store,reply){
 const elements=new Map(),calls=[],answers=[];
 const q=id=>{if(!elements.has(id))elements.set(id,{hidden:true,disabled:false,textContent:''});return elements.get(id)};
 const s={URL,location:{href:'http://localhost/editor?workspace='+workspace},AbortController,Response,SOURCE_PROJECT:'/project',document:{getElementById:q},sessionStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},fetch:async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return reply(url,JSON.parse(options.body));},setTimeout:(fn,ms)=>{if(ms<10000)queueMicrotask(fn);return 1},clearTimeout(){},loadCaps:async()=>{},ksAdd:text=>answers.push(text)};
 s.window=s;vm.runInNewContext(code,s);return {s,q,calls,answers};
}
const response=j=>({ok:true,status:200,json:async()=>j});
(async()=>{
 const key='studioTask:one',store=new Map([[key,JSON.stringify({id:'job',action:'chatbot'})]]);let offline=true;
 const p=page('one',store,()=>{if(offline)throw Error('offline');return response({ok:true,state:'done',project:'/project',result:{reply:'recovered'}})});
 await p.s.studioResumeJobs();assert(store.has(key));assert(!p.q('studioJobResume').hidden);
 const other=page('two',store,()=>{throw Error('must not poll other workspace')});await other.s.studioResumeJobs();assert.equal(other.calls.length,0);
 offline=false;await p.s.studioResumeJobs();assert(!store.has(key));assert.deepEqual(p.answers,['recovered']);
 store.set(key,JSON.stringify({id:'wrong',action:'chatbot'}));const wrong=page('one',store,()=>response({ok:true,state:'done',project:'/different',result:{reply:'do not show'}}));await wrong.s.studioResumeJobs();assert(store.has(key));assert.equal(wrong.answers.length,0);assert(wrong.q('studioJobText').textContent.includes('โปรเจกต์อื่น'));
 const missing=page('one',store,()=>response({ok:false,code:'job_not_found',error:'missing'}));await missing.s.studioResumeJobs();assert(!store.has(key));
 store.set(key,'{corrupt');await missing.s.studioResumeJobs();assert(!store.has(key));
 store.set(key,JSON.stringify({id:'keep',action:'chatbot'}));const auth=page('one',store,()=>({ok:false,status:401}));await auth.s.studioResumeJobs();assert(store.has(key));
 store.set(key,JSON.stringify({id:'done',action:'chatbot'}));const failingLoad=page('one',store,()=>response({ok:true,state:'done',project:'/project',result:{reply:'keep me'}}));failingLoad.s.loadCaps=async()=>{throw Error('load failed')};await failingLoad.s.studioResumeJobs();assert(store.has(key),'must not lose result before captions reload succeeds');
 const legacyStore=new Map([['studioTask',JSON.stringify({id:'legacy',action:'chatbot'})]]);
 const legacy=page('legacyTab',legacyStore,()=>response({ok:true,state:'done',project:'/project',result:{reply:'old result'}}));await legacy.s.studioResumeJobs();assert.equal(legacy.answers[0],'old result');assert.equal(legacyStore.size,0);
 legacyStore.set('studioTask',JSON.stringify({id:'old-other',action:'chatbot'}));const legacyOther=page('newTab',legacyStore,()=>response({ok:true,state:'done',project:'/other',result:{reply:'private'}}));await legacyOther.s.studioResumeJobs();assert(legacyStore.has('studioTask'));assert(!legacyStore.has('studioTask:newTab'));assert.equal(legacyOther.answers.length,0);
 console.log('Studio jobs: workspace isolation, offline/auth resume, wrong-project result protection, missing/corrupt receipts and failed caption reload passed');
})().catch(e=>{console.error(e);process.exit(1)});
