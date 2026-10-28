import sys,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import capcut_session as S,event_timeline as T
from types import SimpleNamespace
class CapCutSessionTests(unittest.TestCase):
 def test_actual_capcut_home_identifiers(self):
  for marker in ['HomePageStartProjectName','HomePageStartProjectDesp']:
   self.assertEqual(S.classify(['CapCut',marker,'HomePageDraftTitle:iSM']),'home')
 def test_actual_home_with_editor_is_rejected(self):
  self.assertEqual(S.classify(['HomePageStartProjectName','MainWindowTitleBarExportBtn']),'editor')
 def test_project_list_alone_is_unknown(self):
  self.assertEqual(S.classify(['HomePageDraftTitle:iSM']),'unknown')
 def test_home(self):self.assertEqual(S.classify(['สร้างโปรเจกต์']),'home')
 def test_editor_wins_over_home(self):self.assertEqual(S.classify(['New project','TimeLineRulerAdsorb']),'editor')
 def test_title_alone_is_unknown(self):self.assertEqual(S.classify(['CapCut']),'unknown')
 def check(self,state,confirmed=False):
  with patch.object(S,'status',return_value={'ok':True,'state':state,'trusted':True,'processes':[]}):T.ensure_closed(confirmed)
 def test_open_app_home_allowed(self):self.check('home')
 def test_editor_rejected_even_with_confirmation(self):
  with self.assertRaises(ValueError):self.check('editor',True)
 def test_editor_process_blocks_inconsistent_home_summary(self):
  with patch.object(S,'status',return_value={'ok':True,'state':'home','processes':[{'state':'editor'}]}):
   with self.assertRaises(ValueError):T.ensure_closed(True)
 def test_unknown_requires_confirmation(self):
  with self.assertRaises(ValueError):self.check('unknown')
  self.check('unknown',True)

class CapCutDiagnosticTests(unittest.TestCase):
 def test_actual_grant_query_false(self):
  ax=MagicMock();ax.AXIsProcessTrusted.return_value=False
  with patch.object(S.ctypes,'CDLL',return_value=ax):self.assertFalse(S.accessibility_trusted())
 def test_permission_error_is_reported_not_classified_as_home(self):
  ax=MagicMock();cf=MagicMock();ax.AXUIElementCreateApplication.return_value=123;cf.CFStringCreateWithCString.return_value=456;ax.AXUIElementCopyAttributeValue.return_value=-25211
  with patch.object(S,'accessibility_trusted',return_value=False),patch.object(S.ctypes,'CDLL',side_effect=[cf,ax]):
   report=S.inspect_process(123,diagnostics=True)
  self.assertEqual(report['state'],'unknown');self.assertFalse(report['trusted']);self.assertEqual(report['ax_errors']['AXWindows'],-25211)
 def test_exception_report_and_legacy_return(self):
  with patch.object(S,'accessibility_trusted',return_value=True),patch.object(S.ctypes,'CDLL',side_effect=OSError('test failure')):
   self.assertEqual(S.inspect_process(123),'unknown');report=S.inspect_process(123,diagnostics=True)
  self.assertTrue(report['trusted']);self.assertIn('OSError',report['reason'])

class CapCutWindowFallbackTests(unittest.TestCase):
 def test_empty_windows_reads_children_with_real_marker(self):
  self.check_roots(False,False)
 def test_launcher_windows_do_not_hide_editor_in_children(self):
  self.check_roots(True,False)
 def test_editor_main_window_is_scanned_with_launcher_windows(self):
  self.check_roots(True,True)
 def check_roots(self,editor,main):
  ax=MagicMock();cf=MagicMock();arrays={200:[400] if editor else [],201:[300],202:[301]};values={700:'CapCut',701:'MainWindowTitleBarExportBtn' if editor else 'HomePageStartProjectName',702:'HomePageStartProjectName'};names={};serial=[800]
  def create(_,raw,encoding):
   serial[0]+=1;names[serial[0]]=raw.decode();return serial[0]
  def attribute(node,key,out):
   table={(1,'AXWindows'):200,(1,'AXChildren'):200 if main else 201,(1,'AXMainWindow'):300 if main else None,(300,'AXTitle'):700,(300,'AXChildren'):202,(301,'AXValue'):701,(400,'AXTitle'):702}
   value=table.get((node,names[key]))
   if value is None:return -25205
   out._obj.value=value;return 0
  def string(value,buffer,size,encoding):buffer.value=values[value].encode();return True
  cf.CFStringCreateWithCString.side_effect=create;cf.CFArrayGetTypeID.return_value=1;cf.CFStringGetTypeID.return_value=2;cf.CFGetTypeID.side_effect=lambda p:1 if p in arrays else 2 if p in values else 3
  cf.CFArrayGetCount.side_effect=lambda p:len(arrays[p]);cf.CFArrayGetValueAtIndex.side_effect=lambda p,i:arrays[p][i];cf.CFStringGetCString.side_effect=string
  ax.AXUIElementCreateApplication.return_value=1;ax.AXUIElementCopyAttributeValue.side_effect=attribute
  with patch.object(S,'accessibility_trusted',return_value=True),patch.object(S.ctypes,'CDLL',side_effect=[cf,ax]):out=S.inspect_process(123,diagnostics=True)
  self.assertEqual(out['state'],'editor' if editor else 'home');self.assertGreaterEqual(out['visited'],2)

class CapCutJobPreflightTests(unittest.TestCase):
 def test_editor_blocks_restore_and_generate_before_worker_or_ai(self):
  from ks import event_jobs as J,event_clip as E
  with patch.object(S,'status',return_value={'ok':True,'state':'editor','processes':[{'state':'editor'}]}),patch.object(J.threading,'Thread') as worker,patch.object(E,'provider_config') as provider:
   for action in ['apply','restore','resegment','proofread_apply','generate','align','silence_apply','history_restore','history_checkpoint']:
    with self.subTest(action=action),self.assertRaises(ValueError):J.start('test','/test',action,{})
  worker.assert_not_called();provider.assert_not_called()
 def test_history_management_is_allowed_while_editor_is_open(self):
  import threading
  from ks import event_jobs as J,feature_tasks as F
  with patch.object(T,'ensure_closed',side_effect=ValueError('editor open')) as gate,patch.object(F,'run',return_value={'ok':True}):
   for action in ['history_clear','history_undo_clear']:
    result=J.start('history-test','/history-test',action,{})
    for thread in threading.enumerate():
     if thread.name.startswith('event-'):thread.join(2)
    self.assertEqual(J.status('history-test',result['job_id'])['state'],'done')
  gate.assert_not_called()
