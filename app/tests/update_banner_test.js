const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('app/ks/editor_page.html','utf8');
const code=html.split('// ─── UPDATE SYSTEM')[1].split('// ─── END UPDATE SYSTEM')[0];
const script=code.slice(code.indexOf('(function(){'));
function page(state,store=new Map()){
 const elements=new Map(),timers=[];let poll;
 const sandbox={document:{getElementById(id){if(!elements.has(id))elements.set(id,{style:{},textContent:''});return elements.get(id);}},localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},fetch:async()=>({ok:true,json:async()=>state}),setInterval:fn=>{poll=fn;return 1},setTimeout:fn=>{timers.push(fn);return timers.length},clearTimeout:()=>{},alert:()=>{}};
 sandbox.window=sandbox;vm.runInNewContext(script,sandbox);
 return {sandbox,elements,timers,poll:()=>poll(),visible:()=>elements.get('update-banner')?.style.display==='flex'};
}
(async()=>{
 const latest={state:'up_to_date',info:{current_version:'1.5.4'}};
 const p=page(latest);await p.poll();assert(!p.visible());
 await p.sandbox.updCheck();assert(p.visible());await p.poll();assert.equal(p.timers.length,1);p.timers[0]();await p.poll();assert(!p.visible());
 const store=new Map(),available={state:'update_available',info:{latest_version:'1.6',release_notes:''}};
 const a=page(available,store);await a.poll();assert(a.visible());a.sandbox.updDismiss();await a.poll();assert(!a.visible());
 const reload=page(available,store);await reload.poll();assert(!reload.visible());await reload.sandbox.updCheck();assert(reload.visible());
 const newer=page({state:'update_available',info:{latest_version:'1.7'}},store);await newer.poll();assert(newer.visible());
 const error=page({state:'error',error:'offline'},store);await error.poll();assert(error.visible());error.sandbox.updDismiss();await error.poll();assert(!error.visible());
 const active=page({state:'downloading',info:{},bytes_total:100,bytes_downloaded:10});await active.poll();assert(active.visible());assert.equal(active.elements.get('upd-dismiss').style.display,'none');
 console.log('Update banner: automatic hide, stable timer, persistent dismiss, manual retry, new version and active progress passed');
})().catch(e=>{console.error(e);process.exit(1)});
