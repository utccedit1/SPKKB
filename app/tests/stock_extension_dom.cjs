const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[2],'utf8');
function page({buttons=[],links=[],account=false,url='https://artlist.io/stock-footage'}={}){
 if(account)links=[...links,{href:'https://artlist.io/downloads/'},{href:'https://artlist.io/favorites/music'}];
 const document={body:{innerText:''},querySelector:s=>account&&s.startsWith('a[href=')?{}:null,
 querySelectorAll:s=>s==='button'?buttons:s==='a[href]'?links:(s==='a,button'||s==='button,a')?[...buttons,...links]:[]};
 const context={getComputedStyle:()=>({display:"block",visibility:"visible"}),document,location:new URL(url),URL,setTimeout:fn=>{fn();}};vm.createContext(context);vm.runInContext(source,context);return context;
}
function button(label,fn=()=>{}){return {innerText:label,disabled:false,getBoundingClientRect:()=>({width:90,height:30}),getAttribute:()=>null,getClientRects:()=>[{}],click:fn};}
(async()=>{
 let p=page({account:true});assert.equal((await p.stockPageTask({action:'status'})).state,'connected');
 p=page();assert.equal((await p.stockPageTask({action:'status'})).state,'needs_login');
 p=page({account:true,buttons:[button('Sign In')]});assert.equal((await p.stockPageTask({action:'status'})).state,'needs_login');
 for(const [kind,format,download] of [['broll','HD','Download'],['music','MP3','direct download']]){
  let clicks=[];const buttons=[button(download,()=>{clicks.push('open');buttons.splice(0,buttons.length,button(format,()=>clicks.push(format)));})];
  p=page({buttons});assert.equal((await p.stockPageTask({action:'download',kind})).clicked,true);assert.deepEqual(clicks,['open',format]);
 }
 const link={href:'https://artlist.io/royalty-free-music/song/peace/123',innerText:'Peace',querySelector:()=>null,getAttribute:()=>null};
 p=page({links:[link],url:'https://artlist.io/royalty-free-music/search?terms=calm%20instrumental'});
 assert.equal((await p.stockPageTask({action:'search',kind:'music',query:'calm instrumental'})).error,'no_match');
 link.innerText='Calm instrumental piano';
 assert.equal((await p.stockPageTask({action:'search',kind:'music',query:'calm instrumental'})).url,link.href);
 const stock={...link,href:'https://artlist.io/stock-footage/clip/students-campus/123',innerText:'Students walking on campus'};
 p=page({links:[stock],url:'https://artlist.io/stock-footage/search?terms=academic%20transcript%20documents'});
 assert.equal((await p.stockPageTask({action:'search',kind:'broll',query:'academic transcript documents',required_terms:['transcript']})).error,'no_match');
 stock.innerText='Academic transcript documents';
 assert.equal((await p.stockPageTask({action:'search',kind:'broll',query:'academic transcript documents',required_terms:['transcript','documents']})).url,stock.href);
 console.log('8 stock DOM regression scenarios passed');
})().catch(e=>{console.error(e);process.exitCode=1});
