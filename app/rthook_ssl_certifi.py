
import os, sys
# แก้ REQUESTS_CA_BUNDLE และ SSL_CERT_FILE ให้ชี้ไป certifi ใน bundle
if hasattr(sys, '_MEIPASS'):
    _cert = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')
    if os.path.exists(_cert):
        os.environ.setdefault('REQUESTS_CA_BUNDLE', _cert)
        os.environ.setdefault('SSL_CERT_FILE', _cert)
        # patch certifi.where() ตรงๆ
        try:
            import certifi
            certifi.where = lambda: _cert
        except Exception:
            pass
