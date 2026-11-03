const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('app/ks/pages.py','utf8');
const fn=source.slice(source.indexOf('window.ksUseGeminiAll = async function'),source.indexOf('window.ksSyncInline = function'));
async function trial(keys,saveOK=true){
 const requests=[],status={textContent:''},button={disabled:false};let reload=0;
 const context={window:{},$q:()=>status,ksLoadRoutes:async()=>{reload++},ksFillBadges:async()=>{},fetch:async(url,options)=>{requests.push({url,options});return{ok:options?saveOK:true,json:async()=>options?(saveOK?{ok:true}:{error:'fixture failure'}):{keys,features:[{id:'autoclip'},{id:'align'},{id:'broll'}]}}}};
 vm.runInNewContext(fn,context);await context.window.ksUseGeminiAll({target:button});return{requests,status,button,reload};
}
(async()=>{
 let r=await trial([]);assert.equal(r.requests.length,1);assert.match(r.status.textContent,/Gemini API key/);assert.equal(r.button.disabled,false);
 r=await trial(['Personal key']);const body=JSON.parse(r.requests[1].options.body);assert.deepEqual(body.routes,{autoclip:{backend:'gemini',key_name:'',model:''},align:{backend:'gemini',key_name:'',model:''},broll:{backend:'gemini',key_name:'',model:''}});assert.equal(r.reload,1);assert.match(r.status.textContent,/บันทึกแล้ว/);
 r=await trial(['Personal key'],false);assert.equal(r.reload,0);assert.match(r.status.textContent,/fixture failure/);assert.equal(r.button.disabled,false);
 console.log('Gemini switch: key readiness, all-feature payload, save errors and controls passed');
})().catch(e=>{console.error(e);process.exit(1)});
