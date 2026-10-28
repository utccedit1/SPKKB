const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
async function run(iconGroup,music=false){
 let clicked=0,hdClicks=0,opened=false,now=0;
 const button=(label,text='')=>({innerText:text,disabled:false,getAttribute:k=>k==='aria-label'?label:null,getClientRects:()=>[{}],getBoundingClientRect:()=>({width:20,height:20}),querySelector:()=>null});
 const icon=button('');icon.querySelector=s=>s==='svg'?{}:null;icon.click=()=>{clicked++;opened=true;};
 const favorite=button('Add to favorites');favorite.parentElement={querySelectorAll:()=>iconGroup?[icon,favorite]:[button('download'),favorite]};
 const hd=button('',music?'\u200bMP3\u200b':'HD');hd.click=()=>hdClicks++;
 const primary=button('direct download');primary.click=icon.click;const player=button('download');
 const doc={body:{innerText:''},querySelector:s=>s==='h1'?{}:null,querySelectorAll:s=>s.includes('iframe')?[]:s==='button'?(opened?[hd]:(music?[primary,player]:[favorite])):[]};
 const context=vm.createContext({document:doc,location:{pathname:'/stock-footage/clip/calendar/1'},getComputedStyle:()=>({}),Date:{now:()=>now++*1000},setTimeout:fn=>fn(),URL});
 vm.runInContext(fs.readFileSync('app/stock_extension/content.js','utf8'),context);
 const result=await vm.runInContext(`stockPageTask({action:'download',kind:'${music?'music':'broll'}'})`,context);
 return {result,clicked,hdClicks};
}
(async()=>{let r=await run(true);assert.equal(r.result.clicked,true);assert.equal(r.clicked,1);assert.equal(r.hdClicks,1);r=await run(false);assert.equal(r.clicked,0);assert.equal(r.hdClicks,0);r=await run(false,true);assert.equal(r.result.clicked,true);assert.equal(r.hdClicks,1);console.log('Downloaded clip icon opens HD; unrelated named controls are never used as fallback');})().catch(e=>{console.error(e);process.exitCode=1;});
