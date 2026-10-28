import sys, tempfile, types, unittest
from pathlib import Path
from unittest.mock import patch, Mock
from ks import stock_accounts as A

class FolderAccess(unittest.TestCase):
 def test_native_picker_is_scoped_to_current_download_folder(self):
  with tempfile.TemporaryDirectory() as folder:
   window=Mock();window.create_file_dialog.return_value=[folder]
   view=types.SimpleNamespace(windows=[window],FileDialog=types.SimpleNamespace(FOLDER=20))
   with patch.dict(sys.modules,webview=view),patch.object(A,'peer',return_value={'download_root':folder}):
    result=A.handle('owner',{'action':'authorize_downloads','provider':'artlist'})
    self.assertTrue(result['ok']);window.create_file_dialog.assert_called_once_with(20,directory=str(Path(folder).resolve()))
    window.create_file_dialog.return_value=[str(Path(folder).parent)]
    with self.assertRaisesRegex(ValueError,'เดียวกับ Chrome'):A.handle('owner',{'action':'authorize_downloads','provider':'artlist'})
    window.create_file_dialog.return_value=None
    self.assertIn('ยกเลิก',A.handle('owner',{'action':'authorize_downloads','provider':'artlist'})['message'])
