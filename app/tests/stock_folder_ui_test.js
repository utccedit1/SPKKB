const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=require('child_process').execFileSync(process.env.PYTHON || 'python3',['-c','from ks.cli_lab_ui import JS; print(JS)'],{env:{...process.env,PYTHONPATH:'app'},encoding:'utf8'}).replace(/<\/?script>/g,'');
const elements=new Map(),requests=[];
function element(id){if(!elements.has(id))elements.set(id,{value:'',checked:true,hidden:false,textContent:'',children:[],listeners:{},addEventListener(name,fn){this.listeners[name]=fn;},replaceChildren(){this.children=[];},appendChild(child){this.children.push(child);},style:{}});return elements.get(id);}
let saved='';
const box={document:{getElementById:element,querySelectorAll:()=>[],createElement:()=>({style:{}})},location:{href:'http://localhost/editor?workspace=fixture'},URL,AbortController,sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},setTimeout,clearTimeout,fetch:async(url,opts)=>{
 let data;if(url.startsWith('/api/browse'))data={path:'/Footage',parent:'/',entries:[{name:'Project A',path:'/Footage/Project A',is_dir:true},{name:'clip.mp4',path:'/Footage/clip.mp4',is_dir:false}]};
 else{const body=JSON.parse(opts.body);requests.push(body);if('folder'in body)saved=body.folder;data={ok:true,folder:saved,destination:'/Footage/Project-123'};}
 return {ok:true,status:200,json:async()=>data};}};
box.window=box;vm.runInNewContext(source,box);
(async()=>{for(let i=0;i<12;i++)await Promise.resolve();assert.match(element('cliLabStockDestination').textContent,/Project-123/);
 await element('cliLabChooseStockFolder').onclick();for(let i=0;i<12;i++)await Promise.resolve();
 assert.equal(element('cliLabFolderList').children.length,2,'only folders and parent shown');
 await element('cliLabFolderUse').onclick();assert.equal(saved,'/Footage');assert.equal(element('cliLabFolderPicker').hidden,true);assert.equal(element('cliLabStockFolder').value,'/Footage');
 console.log('Stock folder UI: load destination, browse directories, select and save project folder passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
