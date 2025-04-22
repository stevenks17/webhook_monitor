import sys
import os
import hmac, hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.utils import verify_hmac


def test_verify_hmac():
    secret = "testsecret"
    body = b'{"foo": "bar"}'
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_hmac(secret, body, signature) is True
    assert verify_hmac(secret, body, "invalidsignature") is False


def test_verify_hmac_empty_secret():
    body = b'{"foo": "bar"}'
    signature = "abc"
    assert not verify_hmac("", body, signature)


def test_verify_hmac_empty_body():
    secret = "testsecret"
    signature = hmac.new(secret.encode(), b"", hashlib.sha256).hexdigest()
    assert verify_hmac(secret, b"", signature)
