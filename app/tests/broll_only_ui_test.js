const assert=require('assert'),vm=require('vm');
const source=require('child_process').execFileSync(process.env.PYTHON||'python3',['-c','from ks.broll_auto_ui import JS; print(JS)'],{env:{...process.env,PYTHONPATH:'app'},encoding:'utf8'}).replace(/<\/?script>/g,'');
function page(reply,store=new Map()){
 const elements=new Map(),calls=[];
 function element(id){if(!elements.has(id))elements.set(id,{value:'',checked:false,hidden:false,disabled:false,textContent:'',children:[],appendChild(v){this.children.push(v);}});return elements.get(id);}
 for(const id of ['brollOnlyApply','brollOnlyCancel','brollOnlyResume'])element(id).hidden=true;
 element('ksBrollKind').value='footage';element('brollOnlyCount').value='8';
 const box={URL,AbortController,location:{href:'http://localhost/editor?workspace=one'},document:{getElementById:element,createElement:()=>({})},sessionStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},setTimeout:(fn,t)=>{if(t<10000)queueMicrotask(fn);return 1;},clearTimeout(){},fetch:async(url,opts)=>{const b=JSON.parse(opts.body);if(b.action==='results')return {ok:true,status:200,json:async()=>({ok:true,results:[]})};calls.push(b);return {ok:true,status:200,json:async()=>reply(b)};}};
 box.window=box;vm.runInNewContext(source,box);return {element,calls,store};
}
const settle=async()=>{for(let i=0;i<50;i++)await Promise.resolve();};
(async()=>{
 const p=page(b=>{if(b.action==='start')return {ok:true,job_id:'job'};if(b.action==='job_status')return {ok:true,state:'done',result:{result_id:'result'}};if(b.action==='result_review')return {ok:true,install_id:'ticket',review_notes:'เพิ่มเฉพาะ B-roll'};if(b.action==='install_commit')return {ok:true,message:'applied'};throw Error('unexpected');});
 await settle();await p.element('brollOnlyStart').onclick();
 assert.equal(p.calls[0].operation,'broll_only');assert.equal(p.calls[0].media_kind,'footage');
 assert(!p.calls.some(b=>b.action==='install_commit'),'review before writing');assert(!p.element('brollOnlyApply').hidden);
 await p.element('brollOnlyApply').onclick();assert(p.calls.some(b=>b.install_id==='ticket'));assert(p.element('brollOnlyStatus').textContent.includes('ใส่เฉพาะ B-roll แล้ว'));
 const invalid=page(()=>({ok:true}));await settle();invalid.element('ksBrollKind').value='meme';await invalid.element('brollOnlyStart').onclick();assert.equal(invalid.calls.length,0);
 invalid.element('ksBrollKind').value='footage';invalid.element('brollOnlyCount').value='31';await invalid.element('brollOnlyStart').onclick();assert.equal(invalid.calls.length,0);
 const key='brollOnlyJob:one';
 const gone=page(()=>({ok:false,code:'job_not_found',error:'gone'}),new Map([[key,JSON.stringify({id:'gone'})]]));await settle();assert(!gone.store.has(key));assert(gone.element('brollOnlyApply').hidden);
 const offline=page(()=>{throw Error('offline');},new Map([[key,JSON.stringify({id:'keep'})]]));await settle();assert(offline.store.has(key));assert(!offline.element('brollOnlyResume').hidden);
 const logs=page(b=>({ok:true,state:'failed',error:'test stop',progress_log:[{time:1000,message:'พร้อม 3/10 ภาพ · ดาวน์โหลด 50%'}]}),new Map([[key,JSON.stringify({id:'logs'})]]));await settle();assert(logs.element('brollOnlyLog').textContent.includes('3/10'));assert(logs.element('brollOnlyLog').textContent.includes('50%'));assert(!logs.element('brollOnlyLog').textContent.includes('test stop'));assert.equal(logs.element('brollOnlyStatus').textContent,'test stop');
 const summary=page(()=>({ok:true,state:'failed',error:'blocked fixture',broll_summary:{attempted:0,skipped:18,prepared:0},progress_log:[]}),new Map([[key,JSON.stringify({id:'summary'})]]));await settle();assert(summary.element('brollOnlyLog').textContent.includes('ข้าม 18'));assert(!summary.element('brollOnlyLog').textContent.includes('blocked fixture'));
 const folder=page(b=>({ok:true,message:b.action}));await settle();await folder.element('brollOnlyFolder').onclick();assert.equal(folder.calls[0].action,'broll_media_folder');
 const failed=page(b=>b.action==='start'?{ok:true,job_id:'failed'}:{ok:true,state:'failed',error:'no stock'});await settle();await failed.element('brollOnlyStart').onclick();assert(!failed.calls.some(b=>b.action==='install_commit'));assert(failed.element('brollOnlyApply').hidden);
 console.log('B-roll only UI: isolated mode, explicit import, validation, missing job, offline recovery and failure guards passed');
})().catch(e=>{console.error(e);process.exit(1);});
