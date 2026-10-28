const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
let now=0,ticks=0;
const ctx=vm.createContext({document:{body:{innerText:''},querySelectorAll:()=>[]},location:new URL('https://artlist.io/stock-footage/search'),URL,Date:{now:()=>now},setTimeout:fn=>{ticks++;now+=60000;fn();}});
vm.runInContext(fs.readFileSync('app/stock_extension/content.js','utf8'),ctx);
(async()=>{for(const action of ['search','download']){now=0;ticks=0;const r=await ctx.stockPageTask({action,kind:'broll',query:'calendar'});assert.equal(r.error,'page_not_ready');assert.equal(ticks,1,'background timer throttling must not multiply the timeout by 40');}console.log('Stock background timeout: search/download stop after wall-clock deadline');})().catch(e=>{console.error(e);process.exitCode=1;});
