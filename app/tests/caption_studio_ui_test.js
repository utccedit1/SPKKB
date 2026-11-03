const assert=require('assert'),vm=require('vm'),cp=require('child_process');
const code=cp.execFileSync(process.env.PYTHON||'python3',['-c','from ks.caption_studio_ui import MODEL_JS; print(MODEL_JS)'],{env:{...process.env,PYTHONPATH:'app'},encoding:'utf8'});
const ctx={};vm.createContext(ctx);vm.runInContext(code,ctx);const M=ctx.CaptionStudioModel;
const a={t:0,scale:.5,alpha:0,dx:-.1,dy:0},b={t:1000000,scale:1,alpha:1,dx:0,dy:0};
assert.equal(M.sample([a,b],.5).scale,.75);assert.equal(M.sample([a,b],2).alpha,1);
assert.deepEqual(Array.from(M.selection('selected',new Set(['a']),[{id:'a'},{id:'b'}])),['a']);
assert.deepEqual(Array.from(M.selection('all',new Set(),[{id:'a'},{id:'b'}])),['a','b']);
const gate=M.gate();const old=gate.next();const current=gate.next();assert(!gate.accepts(old));assert(gate.accepts(current));
console.log('Caption studio: shared linear interpolation, selected/all scope and stale-response gate passed');
const ui=cp.execFileSync(process.env.PYTHON||'python3',['-c','from ks.caption_studio_ui import JS; print(JS)'],{env:{...process.env,PYTHONPATH:'app'},encoding:'utf8'}).replace(/<\/?script>/g,'');
function fixture(){
 const elements=new Map(),calls=[],fonts=[];
 function el(id){if(!elements.has(id))elements.set(id,{id,value:'',children:[],hidden:false,dataset:{},style:{setProperty(){}},classList:{toggle(){}},append(...c){this.children.push(...c)},replaceChildren(...c){this.children=c},setAttribute(){},removeAttribute(){},addEventListener(k,f){this[k]=f},querySelector(){return {checked:false}},pause(){},load(){},getContext(){return {clearRect(){},save(){},restore(){},translate(){},scale(){},measureText(t){return {width:t.length*10}},strokeText(){},fillText(){}}}});return elements.get(id);}
 for(const [k,v] of Object.entries({csSize:'8',csY:'-.6',csColor:'#ffffff',csAccent:'#ff5252',csEntry:'.32',csKeyword:'',csSeek:'0'}))el(k).value=v;
 const sandbox={URL,location:{href:'http://localhost/editor?workspace=fixture'},requestAnimationFrame(){},performance:{now:()=>0},FontFace:class{load(){return new Promise((resolve,reject)=>fonts.push({resolve,reject}))}},document:{addEventListener(){},getElementById:el,createElement:()=>el('new'+elements.size),querySelectorAll:()=>[],querySelector:()=>({value:'selected'}),fonts:{add(){}}},fetch:async(url,opts)=>{const b=JSON.parse(opts.body);calls.push(b);let j;if(b.action==='metadata')j={ok:true,source_hash:'h',media_hash:'m',canvas:{width:1080,height:1920},cues:[{id:'a',text:'test',start:0,duration:4}],presets:[],fonts:[{name:'test',path:'/fake.ttf'}],defaults:{font:'/fake.ttf'}};else if(b.action==='style')j={ok:true,settings:{...b.settings,stroke:true,font:'/fake.ttf'},text:'test',layout:{x:0,y:0,scale:1},motion:[a,{...b,t:1000000,scale:1,alpha:1,dx:0,dy:0}]};else j={ok:true,message:'ready'};return {ok:true,json:async()=>j}}};sandbox.window=sandbox;vm.runInNewContext(ui,sandbox);return {el,calls,fonts};
}
const settle=async()=>{for(let i=0;i<20;i++)await Promise.resolve()};
(async()=>{
 const f=fixture();await f.el('csLoad').onclick();await settle();assert.equal(f.fonts.length,1);
 await f.el('csPrepare').onclick();assert(!f.calls.some(c=>c.action==='prepare'),'copy must wait until font preview succeeds');
 f.el('csKeyword').value='new';f.el('csKeyword').input();await settle();assert.equal(f.fonts.length,2);
 f.fonts[1].resolve({});await settle();f.fonts[0].reject(Error('old font failed'));await settle();
 await f.el('csPrepare').onclick();assert(f.calls.some(c=>c.action==='prepare'),'old failed font must not invalidate newest successful preview');
 console.log('Caption studio async: font readiness gates copies; stale font failure preserves latest preview passed');
})().catch(e=>{console.error(e);process.exitCode=1});
