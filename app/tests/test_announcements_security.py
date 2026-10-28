import sys,json,tempfile,os,unittest
from pathlib import Path
from unittest.mock import patch
from html.parser import HTMLParser
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import announcements as A,server as S,pages

class AnnouncementSecurityTests(unittest.TestCase):
 def handler(self,data=None):
  h=object.__new__(S.Handler);h.headers={'Host':'127.0.0.1'};h.path='/api/public_announcements';h._authed=lambda:False;h._is_admin=lambda:True;h._body=lambda:data
  h.replies=[];h._send=lambda value,**kw:h.replies.append((value,kw));return h
 def test_invalid_type_rejected_without_replacing_existing_records(self):
  for payload in ({'title':'fixture','type':'info"><img onerror=fixture>'},{'announcements':[{'text':'fixture','type':'info"><img>'}]}):
   with self.subTest(payload=payload),tempfile.TemporaryDirectory() as tmp,patch.object(S,'_ANN_FILE',tmp+'/ann.json'),patch.object(S,'_gh_token_load',return_value=''),patch.object(S.update_manager,'get_status',return_value={'state':'idle'}):
    file=Path(S._ANN_FILE);file.write_text('[{"type":"info","text":"existing"}]');before=file.read_bytes();h=self.handler(payload)
    h._route_post('/api/admin/announcements/save');self.assertEqual(h.replies[0][1]['code'],400);self.assertEqual(file.read_bytes(),before)
 def test_old_records_are_normalized_and_unknown_fields_excluded(self):
  value=A.normalize([None,{'type':'malformed','text':'<b>literal</b>','token':'fixture-private','ts':float('inf')}])
  self.assertEqual(value,[{'type':'info','text':'<b>literal</b>'}])
 def test_both_schemas_and_multiline_survive_normalization(self):
  value=A.normalize([{'id':'one','type':'warn','title':'หัวข้อ','body':'บรรทัด 1\nบรรทัด 2','date':'"quoted"','ts':123},{'type':'info','text':'legacy'}],strict=True)
  self.assertEqual(value[0]['text'],'หัวข้อ\nบรรทัด 1\nบรรทัด 2');self.assertEqual(value[0]['id'],'one');self.assertEqual(A.normalize(value,strict=True),value)
 def test_public_announcements_use_only_bundled_public_content(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(A.sys,'_MEIPASS',tmp,create=True):
   Path(tmp,'version.json').write_text(json.dumps({'announcements':[{'type':'info','text':'public','token':'fixture-private'}]}))
   h=self.handler()
   with patch.object(S,'_ann_load',side_effect=AssertionError('local records must remain private')),patch.dict(os.environ,{'KS_APP_MODE':'0'}):h.do_GET()
   self.assertEqual(h.replies[0][0],{'announcements':[{'type':'info','text':'public'}]})
   h.path='/api/announcements'
   with patch.dict(os.environ,{'KS_APP_MODE':'0'}):h.do_GET()
   self.assertEqual(h.replies[-1][1]['code'],401)
 def test_oversized_or_malformed_save_is_rejected(self):
  for value in ({},[{'type':'warn','text':{}}],[{'text':'a'*9001}],[{}]*201):
   with self.assertRaises(ValueError):A.normalize(value,strict=True)
 def test_assembled_editor_has_unique_ids(self):
  class Ids(HTMLParser):
   def __init__(self):super().__init__();self.ids=[]
   def handle_starttag(self,tag,attrs):self.ids.extend(v for k,v in attrs if k=='id')
  p=Ids();p.feed(pages.build_editor_page(Path('app/ks/editor_page.html').read_text()))
  self.assertEqual(len(p.ids),len(set(p.ids)))
