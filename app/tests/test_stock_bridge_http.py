"""Browser/extension boundary checks without opening user accounts."""
import unittest
from unittest.mock import Mock, patch
from ks.server import Handler
from ks import stock_accounts

ORIGIN = 'chrome-extension://' + 'a' * 32

class BridgeHTTPTests(unittest.TestCase):
    def handler(self, origin=None):
        handler = Handler.__new__(Handler)
        handler.path = '/api/stock_bridge'
        handler.headers = {'Host': '127.0.0.1:8765', 'Authorization': 'Bearer fixture',
                           'X-Stock-Extension-Origin': ORIGIN}
        if origin is not None:
            handler.headers['Origin'] = origin
        handler._send = Mock()
        handler._body = Mock(return_value={'action': 'poll'})
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        return handler

    def test_service_worker_without_origin_uses_scoped_identity_and_bearer(self):
        handler = self.handler()
        with patch.object(stock_accounts, 'bridge', return_value={'ok': True}) as bridge:
            handler.do_POST()
        bridge.assert_called_once_with('fixture', ORIGIN, {'action': 'poll'})
        handler._send.assert_called_once_with({'ok': True})

    def test_web_origin_cannot_claim_extension_identity(self):
        handler = self.handler('https://untrusted.example')
        with patch.object(stock_accounts, 'bridge') as bridge:
            handler.do_POST()
        bridge.assert_not_called()
        self.assertEqual(handler._send.call_args.kwargs['code'], 403)

    def test_preflight_is_limited_to_extension_bridge(self):
        handler = self.handler(ORIGIN)
        handler.do_OPTIONS()
        handler.send_response.assert_called_once_with(204)
        handler.send_header.assert_any_call('Access-Control-Allow-Origin', ORIGIN)
        for origin, path in [('https://untrusted.example', '/api/stock_bridge'),
                             (ORIGIN, '/api/stock_accounts')]:
            handler = self.handler(origin)
            handler.path = path
            handler.do_OPTIONS()
            self.assertEqual(handler._send.call_args.kwargs['code'], 403)

    def test_invalid_bearer_still_rejected(self):
        handler = self.handler()
        with patch.object(stock_accounts, 'bridge', side_effect=ValueError('invalid')):
            handler.do_POST()
        self.assertEqual(handler._send.call_args.kwargs['code'], 403)
