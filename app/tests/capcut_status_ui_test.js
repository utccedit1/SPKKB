const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const raw=fs.readFileSync('app/ks/studio_workflow.py','utf8');
const start=raw.indexOf("const cb=document.createElement('button');cb.className='ghost';cb.textContent='ตรวจสถานะ CapCut'");
const end=raw.indexOf("const host=document.querySelector('.ks-sidebar')",start);
assert(start>=0&&end>start);const code=raw.slice(start,end);
async function run(data){
 const els=new Map(),timers=[];function element(tag){return {tag,className:'',style:{cssText:'legacy-fixed'},textContent:'',hidden:false,children:[],attrs:{},setAttribute(k,v){this.attrs[k]=v},scrollIntoView(){this.scrolled=true},append(...children){for(const child of children){this.children.push(child);if(child.id)els.set(child.id,child)}}}}
 const system=element('div'),top=element('div'),setup=element('button');setup.id='setupReopen';els.set('studioSystemControls',system);els.set('setupReopen',setup);
 const context={document:{createElement:element,getElementById:id=>els.get(id)||null,querySelector:s=>s==='.ks-topbar2'?top:null},fetch:async()=>({ok:true,json:async()=>data}),setTimeout:(fn)=>{timers.push(fn);return timers.length},clearTimeout(){},window:{updCheck(){}},msg(){}};
 vm.runInNewContext(code,context);const button=system.children.find(x=>x.textContent==='ตรวจสถานะ CapCut');assert(button,'status button belongs in system menu');assert.equal(top.children.length,0);assert(system.children.includes(setup),'setup belongs in system menu');assert.equal(setup.style.cssText,'');await button.onclick();return {panel:els.get('capcutDiagnostic'),timers,system};
}
(async()=>{
 let home=await run({state:'home',trusted:true});assert(home.panel.textContent.includes('อยู่หน้าหลัก'));assert.equal(home.panel.className,'capcut-diagnostic success');assert.equal(home.panel.attrs.role,'status');assert.equal(home.timers.length,1);home.timers[0]();assert(home.panel.hidden);
 let editor=await run({state:'editor',trusted:true});assert(editor.panel.textContent.includes('บันทึก'));assert.equal(editor.panel.className,'capcut-diagnostic warning');assert.equal(editor.timers.length,0);assert(editor.panel.scrolled,'warning should scroll into view');
 let access=await run({state:'home',trusted:false});assert.equal(access.panel.className,'capcut-diagnostic warning');
 let unknown=await run({state:'unknown',trusted:null});assert.equal(unknown.panel.className,'capcut-diagnostic warning');
 assert.equal(editor.panel.children[0].tag,'details');console.log('CapCut status: system menu, ready auto-hide and persistent warnings passed');
})().catch(e=>{console.error(e);process.exit(1)});
