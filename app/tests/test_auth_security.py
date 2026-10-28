import io,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ks import auth as A

class SecurityTests(unittest.TestCase):
 def setUp(self):
  A.SESSIONS.clear()
  self.identity={'uid':'u1','email':'user@example.com','idToken':'verified','refreshToken':'revocable'}
  self.quota={'is_admin':False,'quota_used':0,'quota_limit':None,'expired_at':None}
 def tearDown(self): A.SESSIONS.clear()
 def test_local_session_cannot_be_forged(self):
  with self.assertRaises(ValueError): A.new_session('local:x','x',True)
 def test_admin_config_cannot_grant_role(self):
  with patch.object(A,'_extra_admin_emails',return_value={'attacker@example.com'}),patch.object(A,'_load_local_users',return_value={'attacker@example.com':{'is_admin':True}}):
   self.assertFalse(A.is_admin_email('attacker@example.com'))
 def test_local_fallback_disabled(self):
  with patch.object(A,'firebase_email_signin',return_value=(False,'offline')),patch.object(A,'local_signin') as local:
   self.assertFalse(A.api_login({'email':'x','password':'y'})[0]['ok']);local.assert_not_called()
 def test_unsigned_remember_file_rejected(self):
  with tempfile.TemporaryDirectory() as d,patch.object(A,'DESKTOP_SESSION_FILE',str(Path(d)/'session')):
   Path(A.DESKTOP_SESSION_FILE).write_text(json.dumps({'uid':'u1','email':'owner@example.com','is_admin':True,'ts':time.time()}))
   self.assertEqual(A.restore_desktop_session(),(None,None))
 def test_restore_uses_verified_identity_not_file_role(self):
  with patch.object(A,'load_desktop_session',return_value={'refresh_token':'r','is_admin':True,'email':'owner@example.com'}),patch.object(A,'_refresh_identity',return_value=self.identity),patch.object(A,'_cloud_license',return_value=self.quota),patch.object(A,'save_desktop_session'):
   token,info=A.restore_desktop_session();self.assertTrue(token);self.assertFalse(info['is_admin']);self.assertEqual(info['email'],'user@example.com')
 def test_refresh_failure_denied(self):
  with patch.object(A,'load_desktop_session',return_value={'refresh_token':'fake'}),patch.object(A,'_refresh_identity',side_effect=ValueError):
   self.assertEqual(A.restore_desktop_session(),(None,None))
 def test_revoked_session_denied(self):
  token=A.new_session('u1','user@example.com',identity=self.identity,quota=self.quota)
  A.SESSIONS[token]['checked_at']=0
  with patch.object(A,'_refresh_identity',side_effect=ValueError): self.assertFalse(A.session_valid(token))
 def test_role_revocation_rechecked(self):
  token=A.new_session('u1','user@example.com',True,identity=self.identity,quota={'is_admin':True})
  A.SESSIONS[token]['checked_at']=0
  with patch.object(A,'_refresh_identity',return_value=self.identity),patch.object(A,'_cloud_license',return_value=self.quota):
   self.assertTrue(A.session_valid(token));self.assertFalse(A.session_user(token)['is_admin'])
 def test_quota_without_verified_identity_denied(self):
  self.assertFalse(A.check_quota('u1','user@example.com')['ok'])
 def test_cloud_failure_denied(self):
  with patch.object(A,'_cloud_license',side_effect=OSError):self.assertFalse(A.check_quota('u1','user@example.com',self.identity)['ok'])
 def test_license_missing_or_inactive_denied(self):
  for fields in ({},{'is_active':{'booleanValue':False}}):
   with patch.object(A,'load_web_config',return_value={'projectId':'fake'}),patch.object(A,'_firebase_request',return_value={'fields':fields}):
    with self.assertRaises(ValueError):A._cloud_license(self.identity)
 def test_malformed_expiry_denied(self):
  fields={'is_active':{'booleanValue':True},'expired_at':{'stringValue':'invalid'}}
  with patch.object(A,'load_web_config',return_value={}),patch.object(A,'_firebase_request',return_value={'fields':fields}):
   with self.assertRaises(ValueError):A._cloud_license(self.identity)
 def test_project_cannot_be_redirected(self):
  fields={'is_active':{'booleanValue':True},'is_admin':{'booleanValue':False}}
  with patch.object(A,'load_web_config',return_value={'projectId':'fake'}),patch.object(A,'_firebase_request',return_value={'fields':fields}) as request:
   A._cloud_license(self.identity);self.assertIn('/projects/capcutauto-9984c/',request.call_args.args[0])
 def test_remember_stores_no_trusted_role(self):
  with tempfile.TemporaryDirectory() as d,patch.object(A,'CONFIG_DIR',d),patch.object(A,'DESKTOP_SESSION_FILE',str(Path(d)/'session')):
   self.assertTrue(A.save_desktop_session('u1','user@example.com',True,self.identity))
   data=json.loads(Path(A.DESKTOP_SESSION_FILE).read_text());self.assertEqual(set(data),{'refresh_token','ts'})
   self.assertEqual(Path(A.DESKTOP_SESSION_FILE).stat().st_mode&0o777,0o600)
 def test_remember_survives_restart_after_two_days_and_rechecks_license(self):
  with tempfile.TemporaryDirectory() as d,patch.object(A,'CONFIG_DIR',d),patch.object(A,'DESKTOP_SESSION_FILE',str(Path(d)/'session')):
   self.assertTrue(A.save_desktop_session('u1','user@example.com',identity=self.identity))
   f=Path(A.DESKTOP_SESSION_FILE);data=json.loads(f.read_text());data['ts']-=2*86400;f.write_text(json.dumps(data));A.SESSIONS.clear()
   with patch.object(A,'_refresh_identity',return_value=self.identity) as refresh,patch.object(A,'_cloud_license',return_value=self.quota) as license:
    token,info=A.restore_desktop_session()
   self.assertTrue(token);self.assertTrue(info['ok']);refresh.assert_called_once_with('revocable');license.assert_called_once_with(self.identity)
 def test_saved_login_expires_after_thirty_days(self):
  with tempfile.TemporaryDirectory() as d,patch.object(A,'DESKTOP_SESSION_FILE',str(Path(d)/'session')):
   f=Path(A.DESKTOP_SESSION_FILE);f.write_text(json.dumps({'refresh_token':'revocable','ts':time.time()-31*86400}))
   with patch.object(A,'_refresh_identity') as refresh:self.assertEqual(A.restore_desktop_session(),(None,None))
   refresh.assert_not_called();self.assertFalse(f.exists())
 def test_remembered_login_cannot_restore_revoked_license(self):
  with patch.object(A,'load_desktop_session',return_value={'refresh_token':'revocable'}),patch.object(A,'_refresh_identity',return_value=self.identity),patch.object(A,'_cloud_license',side_effect=ValueError('revoked')):
   self.assertEqual(A.restore_desktop_session(),(None,None));self.assertFalse(A.SESSIONS)
 def login_with_remember(self,remember):
  with patch.object(A,'firebase_email_signin',return_value=(True,{'idToken':'verified','refreshToken':'revocable'})),patch.object(A,'_verified_identity',return_value=dict(self.identity)),patch.object(A,'check_quota',return_value={'ok':True,'quota':self.quota}):
   return A.api_login({'email':'user@example.com','password':'not-saved','remember':remember})
 def test_unchecking_remember_removes_previous_saved_login(self):
  with tempfile.TemporaryDirectory() as d,patch.object(A,'CONFIG_DIR',d),patch.object(A,'DESKTOP_SESSION_FILE',str(Path(d)/'session')):
   self.assertTrue(self.login_with_remember(True)[0]['remembered']);self.assertTrue(Path(A.DESKTOP_SESSION_FILE).exists())
   reply,token=self.login_with_remember(False);self.assertTrue(reply['ok']);self.assertTrue(token);self.assertFalse(reply['remembered']);self.assertFalse(Path(A.DESKTOP_SESSION_FILE).exists())
 def test_failed_save_is_reported_and_does_not_leave_previous_account(self):
  with patch.object(A,'save_desktop_session',return_value=False),patch.object(A,'clear_desktop_session') as clear:
   reply,token=self.login_with_remember(True)
  self.assertTrue(reply['ok']);self.assertTrue(token);self.assertFalse(reply['remembered']);self.assertIn('warning',reply);clear.assert_called_once()
 def test_signup_disabled(self):self.assertFalse(A.api_signup_local({'setup_code':'anything'})['ok'])

class BrowserBoundaryTests(unittest.TestCase):
 def test_cross_origin_and_fake_host_denied(self):
  from ks.server import Handler
  from types import SimpleNamespace
  for headers in ({'Host':'evil.example:8765','Content-Type':'application/json'},
                  {'Host':'127.0.0.1:8765','Origin':'https://evil.example','Content-Type':'application/json'},
                  {'Host':'127.0.0.1:8765','Content-Type':'application/jsonp'}):
   self.assertFalse(Handler._csrf_ok(SimpleNamespace(headers=headers)))
 def test_same_origin_allowed(self):
  from ks.server import Handler
  from types import SimpleNamespace
  headers={'Host':'127.0.0.1:8765','Origin':'http://127.0.0.1:8765','Content-Type':'application/json; charset=utf-8'}
  self.assertTrue(Handler._csrf_ok(SimpleNamespace(headers=headers)))

if __name__=='__main__':unittest.main()
