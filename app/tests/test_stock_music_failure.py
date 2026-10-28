import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ks import stock_accounts as A,stock_media as M
class MusicFailure(unittest.TestCase):
 def test_optional_music_error_keeps_edit_and_reports_missing_music(self):
  with tempfile.TemporaryDirectory() as folder:
   Path(folder,'draft_info.json').write_text(json.dumps({'duration':10000000,'tracks':[]}))
   plan={'auto_stock':True,'stock_provider':'artlist','stock_requests':[{'kind':'music','query':'calm instrumental','start':0}]}
   with patch.object(A,'wait_download',side_effect=A.StockDownloadError('search unavailable','search_failed')):
    M.apply(folder,plan,'owner',lambda *a:None,lambda m:None)
   rows=json.loads(Path(folder,'stock_report.json').read_text());self.assertEqual(rows[0]['state'],'skipped');self.assertIn('ไม่มีเพลง',rows[0]['reason'])
 def test_cancellation_is_not_treated_as_optional_music_failure(self):
  with tempfile.TemporaryDirectory() as folder:
   Path(folder,'draft_info.json').write_text(json.dumps({'duration':10000000,'tracks':[]}))
   plan={'auto_stock':True,'stock_provider':'artlist','stock_requests':[{'kind':'music','query':'calm','start':0}]}
   with patch.object(A,'wait_download',side_effect=A.StockDownloadError('cancelled','cancelled')):
    with self.assertRaisesRegex(A.StockDownloadError,'cancelled'):M.apply(folder,plan,'owner',lambda *a:None,lambda m:None)

class DownloadCache(unittest.TestCase):
 def test_reuse_requires_owner_folder_matching_query_and_digest(self):
  from ks import stock_browser as B
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);media=root/'media';media.mkdir();f=media/'asset.mp3';f.write_bytes(b'audio')
   row=dict(provider='artlist',kind='music',query='calm instrumental',url='https://artlist.io/royalty-free-music/song/calm/123',path=str(f),sha256='good',title='Calm')
   f.with_suffix('.mp3.stock.json').write_text(json.dumps(row))
   with patch.object(A,'peer',return_value={'root':root}),patch.object(B,'verify_file',return_value=dict(sha256='good',duration=8,size=5)):
    self.assertIsNotNone(A.cached_download('owner','artlist',dict(kind='music',query='calm instrumental')))
    self.assertIsNone(A.cached_download('owner','artlist',dict(kind='music',query='different')))
   with patch.object(A,'peer',return_value={'root':root}),patch.object(B,'verify_file',return_value=dict(sha256='changed',duration=8,size=5)):
    self.assertIsNone(A.cached_download('owner','artlist',dict(kind='music',query='calm instrumental')))

 def test_short_visual_query_reuses_verified_footage_and_honors_exclusions(self):
  from ks import stock_browser as B
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);media=root/'media';media.mkdir();f=media/'asset.mp4';f.write_bytes(b'video')
   row=dict(provider='artlist',kind='broll',query='a longer old supermarket search',url='https://artlist.io/stock-footage/clip/cashier/123',path=str(f),sha256='good',title='Shop Employee Cashier Supermarket')
   f.with_suffix('.mp4.stock.json').write_text(json.dumps(row));request=dict(kind='broll',query='supermarket cashier',required_terms=['cashier'])
   with patch.object(A,'peer',return_value={'root':root}),patch.object(B,'verify_file',return_value=dict(sha256='good',duration=8,size=5)):
    self.assertIsNotNone(A.cached_download('owner','artlist',request))
    self.assertIsNone(A.cached_download('owner','artlist',dict(request,exclude_hashes=['good'])))
    self.assertIsNone(A.cached_download('owner','artlist',dict(request,query='stamp loyalty',required_terms=['stamp'])))


class FootageRecovery(unittest.TestCase):
 def test_failed_search_tries_approved_alternative_and_continues_next_cue(self):
  with tempfile.TemporaryDirectory() as folder:
   original={'duration':30000000,'tracks':[]};Path(folder,'draft_info.json').write_text(json.dumps(original))
   plan={'auto_stock':True,'stock_provider':'artlist','stock_requests':[{'kind':'broll','query':'game progress','start':4,'alternatives':[{'query':'achievement badge','required_terms':['badge']}]},{'kind':'broll','query':'customer shopping','start':14}]}
   with patch.object(A,'wait_download',side_effect=[A.StockDownloadError('not hydrated','page_not_ready'),None,None]) as acquire:
    M.apply(folder,plan,'owner',lambda *a:None,lambda m:None)
   self.assertEqual(acquire.call_count,3);self.assertEqual(acquire.call_args_list[1].args[2]['query'],'achievement badge')
   self.assertEqual(json.loads(Path(folder,'draft_info.json').read_text()),original)
   rows=json.loads(Path(folder,'stock_report.json').read_text());self.assertEqual(len(rows),2);self.assertIn('not hydrated',rows[0]['reason'])
 def test_captcha_does_not_trigger_alternative_or_silent_skip(self):
  with tempfile.TemporaryDirectory() as folder:
   Path(folder,'draft_info.json').write_text(json.dumps({'duration':30000000,'tracks':[]}))
   plan={'auto_stock':True,'stock_provider':'artlist','stock_requests':[{'kind':'broll','query':'game progress','start':4}]}
   with patch.object(A,'wait_download',side_effect=A.StockDownloadError('human required','captcha')) as acquire:
    with self.assertRaises(A.StockDownloadError):M.apply(folder,plan,'owner',lambda *a:None,lambda m:None)
   self.assertEqual(acquire.call_count,1)
