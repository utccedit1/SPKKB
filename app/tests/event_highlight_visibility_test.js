const fs=require('fs'),assert=require('assert/strict'),vm=require('vm');
const raw=fs.readFileSync('app/ks/event_clip_ui.py','utf8');
const ui=raw.slice(raw.indexOf("EVENT_UI ="),raw.indexOf('<script>'));
assert.match(ui,/<details[^>]*id="evTopicsDetails"/,'long topic list must be collapsible');
assert(ui.indexOf('id="evPlan"')<ui.indexOf('id="evStatus"'),'status must follow planning controls');
assert(ui.indexOf('id="evStatus"')<ui.indexOf('id="evReview"'),'status must appear before long review');
const code=raw.slice(raw.indexOf('async function evWatch(action)'),raw.indexOf("window.addEventListener('DOMContentLoaded'"));
let scrolled=0;const elements=new Map();function el(id){if(!elements.has(id))elements.set(id,{textContent:'',value:0,max:0,scrollIntoView(){scrolled++}});return elements.get(id)}
const ctx={evJob:'fixture',evPolling:false,Date,document:{getElementById:el},evPost:async()=>({state:'done',message:'done',completed:1,total:1,created:Date.now()/1000,backend:'fixture',result:{}}),evClock:()=>'',sessionStorage:{removeItem(){}},evBusy(){},evShow(){},setTimeout};
vm.runInNewContext(code,ctx);(async()=>{await ctx.evWatch('plan');assert.equal(scrolled,1,'completed plan must reveal its review');assert(el('evStatus').textContent.includes('วางแผนเสร็จ'));console.log('Highlight plan visibility passed')})().catch(e=>{console.error(e);process.exit(1)});
