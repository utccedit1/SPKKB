const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
let clicks=0;const url='https://artlist.io/stock-footage/clip/calendar/123';const a={href:url,click:()=>clicks++};
const ctx=vm.createContext({URL,Date,location:new URL('https://artlist.io/stock-footage/search?terms=calendar'),document:{body:{innerText:''},querySelectorAll:s=>s==='a[href]'?[a]:[]}});
vm.runInContext(fs.readFileSync('app/stock_extension/content.js','utf8'),ctx);
(async()=>{assert.equal((await ctx.stockPageTask({action:'open_clip',url})).navigated,true);assert.equal(clicks,1);for(const target of ['https://example.com/stock-footage/clip/calendar/123',url+'?redirect=1','https://artlist.io/account'])assert.equal((await ctx.stockPageTask({action:'open_clip',url:target})).error,'invalid_url');assert.equal(clicks,1);assert.equal((await ctx.stockPageTask({action:'open_clip',url:url+'4'})).error,'missing_link');let submits=0;
 class Input{set value(v){this.current=v;}getClientRects(){return [{}];}getAttribute(name){return name==='role'?'combobox':null;}dispatchEvent(){}}
 const input=new Input();input.form={requestSubmit:()=>submits++};
 ctx.HTMLInputElement=Input;ctx.Event=class{constructor(type){this.type=type;}};
 ctx.document.querySelectorAll=selector=>selector==='input'?[input]:[];
 assert.equal((await ctx.stockPageTask({action:'search_route',query:'calendar dates'})).navigated,true);
 assert.equal(input.current,'calendar dates');assert.equal(submits,1);
 assert.equal((await ctx.stockPageTask({action:'search_route',query:'https://bad.test'})).error,'invalid_query');assert.equal(submits,1);
 const unrelated={href:'https://artlist.io/stock-footage/clip/text-date-archive-8mm/6106261',innerText:'Text Date Archive 8mm',querySelector:()=>null,getAttribute:()=>null};
 ctx.setTimeout=fn=>fn();ctx.document.querySelectorAll=selector=>selector==='a[href]'?[unrelated]:[];
 assert.equal((await ctx.stockPageTask({action:'search',kind:'broll',query:'calendar'})).error,'no_match','date text is not a calendar visual');
 console.log('Stock navigation: actual catalog links, native search form, scoped routes, calendar relevance');})().catch(e=>{console.error(e);process.exitCode=1;});
