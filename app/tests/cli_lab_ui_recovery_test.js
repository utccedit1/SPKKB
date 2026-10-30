const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=require('child_process').execFileSync(process.env.PYTHON || 'python3',['-c','from ks.cli_lab_ui import JS; print(JS)'],{env:{...process.env,PYTHONPATH:'app'},encoding:'utf8'}).replace(/<\/?script>/g,'');
const key='cliLabActiveJob:workspace';
function page(reply,store=new Map(),results=[]){
 const elements=new Map(),calls=[];
 function element(id){if(!elements.has(id))elements.set(id,{value:'',checked:true,hidden:false,disabled:false,textContent:'',children:[],appendChild(child){this.children.push(child);},listeners:{},addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);},focus(){this.focused=true;}});return elements.get(id);}
 element('cliLabMode').value='story';element('cliLabMin').value='30';element('cliLabMax').value='45';
 const box={document:{createElement:()=>({children:[],appendChild(child){this.children.push(child);}}),getElementById:element,querySelectorAll:()=>[...elements.values()]},location:{href:'http://localhost/editor?workspace=workspace'},URL,AbortController,sessionStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},setTimeout:(fn,ms)=>{if(ms<10000)queueMicrotask(fn);return 1;},clearTimeout(){},fetch:async(url,opts)=>{const body=JSON.parse(opts.body);if(body.action==='results')return {ok:true,status:200,json:async()=>({ok:true,results})};if(body.action==='stock_settings')return {ok:true,status:200,json:async()=>({ok:true,folder:'',destination:'/fixture/project/media'})};calls.push(body);return reply(body,calls.length);}};
 box.window=box;vm.runInNewContext(source,box);return {box,element,calls,store};
}
const ok=data=>({ok:true,status:200,json:async()=>({ok:true,...data})});
const settle=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
(async()=>{
 const presets=page(()=>ok({}));
 const choose=presets.element('cliLabPromptTemplate'),brief=presets.element('cliLabInstruction');
 assert.equal(choose.value,'social');assert(brief.value.includes('ไม่แต่งคำพูด'));
 brief.value='คำสั่งที่ฉันแก้เอง';for(const fn of brief.listeners.input)fn();
 choose.value='knowledge';for(const fn of choose.listeners.change)fn();assert(brief.value.includes('ความรู้'));
 choose.value='social';for(const fn of choose.listeners.change)fn();assert.equal(brief.value,'คำสั่งที่ฉันแก้เอง');
 choose.value='custom';for(const fn of choose.listeners.change)fn();assert.equal(brief.value,'');
 brief.value='สรุปเรื่องนี้';for(const fn of brief.listeners.input)fn();
 const restored=page(()=>ok({}),presets.store);assert.equal(restored.element('cliLabInstruction').value,'สรุปเรื่องนี้');
 assert.equal(presets.element('cliLabMin').value,'30');assert.equal(presets.element('cliLabMax').value,'45');
 const stored=new Map([[key,JSON.stringify({id:'job1',action:'setup_alignment'})]]);
 let offline=true;
 const p=page(()=>{if(offline)throw Error('offline');return ok({state:'done',result:{output:'ready'}});},stored);
 await settle();assert(stored.has(key),'network failure must keep job');assert(!p.element('cliLabResume').hidden);
 offline=false;await p.box.cliLabResumeJob();assert(!stored.has(key));assert(p.element('cliLabResult').textContent.includes('ready'));assert(p.element('cliLabResume').hidden);
 const q=page(()=>ok({}));q.element('cliLabInstruction').value='';await q.box.cliLab('plan');assert.equal(q.calls.length,0);assert(q.element('cliLabInstruction').focused);
 q.element('cliLabInstruction').value='make a clip';q.element('cliLabMin').value='80';q.element('cliLabMax').value='30';await q.box.cliLab('plan');assert.equal(q.calls.length,0);
 const token='a'.repeat(32);let fail=false;
 const s=page(b=>{if(fail)throw Error('scan failed');if(b.action==='storage_preview')return ok({cleanup_id:token,note:'preview',files:[{name:'old',size:1}],total_bytes:1});if(b.action==='storage_move')return ok({cleanup_id:token,message:'moved'});return ok({message:'restored'});});
 await s.box.cliLabStorage('preview');await s.box.cliLabStorage('move');assert(!s.element('cliStorageRestore').hidden);
 await s.box.cliLabStorage('preview');fail=true;await s.box.cliLabStorage('preview');assert(s.element('cliStorageMove').hidden,'failed preview must invalidate old move');
 fail=false;await s.box.cliLabStorage('restore');assert.equal(s.calls.at(-1).cleanup_id,token);assert(s.element('cliStorageRestore').hidden);
 const r=page(()=>({ok:false,status:404,json:async()=>({error:'gone'})}),new Map([[key,JSON.stringify({id:'gone',action:'plan'})]]));await settle();assert(!r.store.has(key));
 const auth=page(()=>({ok:false,status:401,json:async()=>({error:'sign in'})}),new Map([[key,JSON.stringify({id:'keep',action:'plan'})]]));await settle();assert(auth.store.has(key),'temporary auth loss must not forget job');
 let operation='plan',previewFails=true;
 const flow=page(b=>{
  if(b.action==='start'){operation=b.operation;return ok({job_id:'flow'});}
  if(b.action==='job_status')return ok({state:'done',result:operation==='plan'?{mode:'single',plan_id:'p',start:0,end:10,reason:'test'}:{destination:'/saved-output',output:'created'}});
  if(b.action==='install_preview'){if(previewFails)throw Error('temporary preview failure');return ok({install_id:'ticket',old_duration:20,new_duration:10});}
  throw Error('unexpected action');
 });
 flow.element('cliLabInstruction').value='test';await flow.box.cliLab('plan');await flow.box.cliLab('apply');
 assert(!flow.element('cliLabPrepareResult').hidden,'completed output needs direct prepare retry');assert.equal(flow.element('cliLabResultFolder').value,'/saved-output');
 previewFails=false;await flow.box.cliLab('install_preview');assert(flow.element('cliLabPrepareResult').hidden);assert(!flow.element('cliLabInstall').disabled);assert(flow.element('cliLabCancel').hidden,'no cancel button for completed/synchronous work');
 const missing=page(()=>ok({ok:false,code:'job_not_found',error:'gone'}),new Map([[key,JSON.stringify({id:'gone',action:'plan'})]]));
 await settle();assert(!missing.store.has(key),'HTTP 200 with job_not_found must end stale tracking');assert(missing.element('cliLabResume').hidden);
 const installStore=new Map([[key,JSON.stringify({id:'ticket1',action:'install_commit'})]]);
 const recoveredInstall=page(b=>{assert.equal(b.action,'job_status');return ok({state:'done',result:{message:'บันทึกแล้ว',warning:'ตรวจพื้นที่จัดเก็บ'}});},installStore);
 await settle();assert(!installStore.has(key));assert(recoveredInstall.element('cliLabResult').textContent.includes('บันทึกแล้ว'));assert(recoveredInstall.element('cliLabResult').textContent.includes('ตรวจพื้นที่จัดเก็บ'));assert(!recoveredInstall.calls.some(b=>b.action==='start'));
 const savedResult={result_id:'saved-result',destination:'/saved-output',created:100,operation:'apply'};
 const reopened=page(b=>{assert.equal(b.action,'result_review');assert.equal(b.result_id,'saved-result');return ok({install_id:'saved-ticket',old_duration:20,new_duration:10});},new Map(),[savedResult]);
 await settle();const savedButton=reopened.element('cliLabSavedResults').children[0].children[0];
 await savedButton.onclick();assert.equal(reopened.element('cliLabResultFolder').value,'/saved-output');assert(!reopened.element('cliLabInstall').disabled);
 const staleResult=page(()=>ok({ok:false,error:'source changed'}),new Map(),[savedResult]);
 await settle();await staleResult.element('cliLabSavedResults').children[0].children[0].onclick();
 assert(staleResult.element('cliLabInstall').disabled);assert(staleResult.element('cliLabResult').textContent.includes('source changed'));
 console.log('CLI UI: offline recovery, explicit resume, terminal missing jobs, auth recovery, validation and cleanup undo isolation passed');
})().catch(e=>{console.error(e);process.exit(1)});
