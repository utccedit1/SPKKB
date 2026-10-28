const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('app/ks/onboarding.py','utf8').split("JS=r'''")[1].split("'''")[0].replace(/<\/?script>/g,'');
function page(reply,pathname='/editor',store=new Map()){const els=new Map(),calls=[];let boot;
const q=id=>{if(!els.has(id))els.set(id,{disabled:false,textContent:'',open:false,showModal(){this.open=true},close(){this.open=false}});return els.get(id)};
const s={location:{pathname},sessionStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},document:{getElementById:id=>id==='tab_main'&&pathname!=='/editor'?null:q(id),addEventListener:(name,fn)=>{boot=fn}},AbortController,setTimeout:()=>1,clearTimeout(){},fetch:async(url,opts)=>{const data=JSON.parse(opts.body);calls.push(data);return {ok:true,json:async()=>reply(data)}}};s.window=s;vm.runInNewContext(code,s);return{s,q,calls,boot};}
(async()=>{
const p=page(d=>d.action==='status'?{ok:true,preferences:{},tools_ready:true,project_ready:true,capcut_installed:true,ai_ready:false,accessibility:false}:({ok:true}));await p.boot();assert(p.q('studioSetup').open);assert(!p.q('setupFinish').disabled);assert(p.q('setupAI').textContent.includes('ยังไม่ตั้งค่า'));await p.s.studioSetupSave('defer');assert.equal(p.calls.at(-1).action,'defer');assert(!p.q('studioSetup').open);
const seen=page(()=>({ok:true,preferences:{seen:true},tools_ready:true,project_ready:true,capcut_installed:true}));await seen.boot();assert(!seen.q('studioSetup').open);await seen.s.studioSetupOpen();assert(seen.q('studioSetup').open);
const bad=page(()=>({ok:true,preferences:{},tools_ready:false,project_ready:true,capcut_installed:true}));await bad.boot();assert(bad.q('setupFinish').disabled);
const missing=page(()=>({ok:true,preferences:{},tools_ready:true,project_ready:true,capcut_installed:false}));await missing.boot();assert(missing.q('setupFinish').disabled);assert(missing.q('setupMessage').textContent.includes('CapCut'));
const navigation=new Map();const first=page(()=>({ok:true,preferences:{},tools_ready:true,project_ready:false,capcut_installed:true}),'/editor',navigation);await first.boot();first.s.studioSetupGo('project');assert.equal(first.s.location.href,'/');
const picker=page(()=>({ok:true,preferences:{},tools_ready:true,project_ready:false,capcut_installed:true}),'/',navigation);await picker.boot();assert(!picker.q('studioSetup').open,'wizard must allow selecting a project without reopening in a loop');
const back=page(()=>({ok:true,preferences:{seen:true},tools_ready:true,project_ready:true,capcut_installed:true}),'/editor',navigation);await back.boot();assert(back.q('studioSetup').open,'resume setup after project selection');assert(!navigation.has('studioSetupPick'));
console.log('Onboarding: first-run, deferred reopening, explicit readiness and missing CapCut guards passed');
})().catch(e=>{console.error(e);process.exit(1)});
