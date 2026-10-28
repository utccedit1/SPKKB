import json,sys,subprocess,shutil,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import feature_tasks as F,chatbot,pages
class AutomaticRefreshTests(unittest.TestCase):
 def test_chat_ignores_stale_or_missing_timeline(self):
  with patch.object(chatbot,'api_chatbot',return_value={'ok':True,'reply':'answer'}) as ai:
   result=F.run('/missing/project','chatbot',{'source_hash':'old','message':'hello'})
  self.assertTrue(result['ok']);ai.assert_called_once()
 def test_generated_javascript_parses(self):
  import re
  html=pages.build_editor_page((Path(__file__).resolve().parents[1]/'ks/editor_page.html').read_text())
  for script in re.findall(r'<script[^>]*>(.*?)</script>',html,re.S):
   r=subprocess.run(['node','--check'],input=script,text=True,capture_output=True);self.assertEqual(r.returncode,0,r.stderr)
 def test_refresh_keeps_identity_not_row_numbers_and_stops_deleted_selection(self):
  source=(Path(__file__).resolve().parents[1]/'ks/editor_page.html').read_text();fn=source[source.index('async function ensureCapsLatest'):source.index('function pick(mode)')]
  harness=r'''
const assert=require('node:assert/strict');
let CAPS=[{index:0,segment_id:'a'},{index:1,segment_id:'b'}],STATE_HASH='old',SOURCE_HASH='old',SOURCE_PROJECT='/p',CAPS_CURRENT=false;
let CAP_SELECTION_TOUCHED=true;
let chosen=[1],checks=[{dataset:{i:'5'},checked:false},{dataset:{i:'6'},checked:false}],loads=0;
let response={state_hash:'new',source_hash:'live',source_project:'/p',captions:[{index:5,segment_id:'b'},{index:6,segment_id:'a'}]};
const selected=()=>chosen;
const fetch=async()=>({ok:true,json:async()=>response});
const document={querySelectorAll:()=>checks};
async function loadCaps(quiet,current){loads++;CAPS=response.captions;STATE_HASH=response.state_hash;SOURCE_HASH=response.source_hash;SOURCE_PROJECT=response.source_project;CAPS_CURRENT=current;return response;}
'''+fn+r'''
(async()=>{
 await ensureCapsLatest(true);assert.equal(checks[0].checked,true);assert.equal(checks[1].checked,false);assert.equal(loads,1);
 response.source_hash='later';await ensureCapsLatest(false);assert.equal(loads,1);assert.equal(SOURCE_HASH,'later');assert.equal(CAPS_CURRENT,false);
 chosen=[5];response={...response,state_hash:'deleted',captions:[{index:0,segment_id:'other'}]};checks=[{dataset:{i:'0'},checked:true}];
 await assert.rejects(ensureCapsLatest(true),/เลือกช่วงใหม่/);assert.equal(checks[0].checked,false);
})().catch(e=>{console.error(e);process.exit(1)});
'''
  result=subprocess.run(['node'],input=harness,text=True,capture_output=True);self.assertEqual(result.returncode,0,result.stderr)
