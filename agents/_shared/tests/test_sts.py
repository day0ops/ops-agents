import base64
import json

from ops_agent import sts


def _jwt(payload: dict) -> str:
    def seg(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{seg({'alg':'none'})}.{seg(payload)}.sig"

def test_decode_claims_reads_nested_act():
    tok = _jwt({"sub": "user", "act": {"sub": "deploy", "act": {"sub": "release-manager"}}})
    c = sts.decode_claims(tok)
    assert c["sub"] == "user"
    assert c["act"]["sub"] == "deploy"
    assert c["act"]["act"]["sub"] == "release-manager"

def test_exchange_posts_verified_shape(monkeypatch):
    captured = {}
    class FakeResp:
        status_code = 200
        def json(self): return {"access_token": "exchanged-token"}
        def raise_for_status(self): pass
    def fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url; captured["data"] = data; captured["headers"] = headers
        return FakeResp()
    monkeypatch.setattr(sts.requests, "post", fake_post)
    out = sts.exchange("http://sts:7777/oauth2/token", "subject-tok", "actor-tok")
    assert out == "exchanged-token"
    assert captured["url"] == "http://sts:7777/oauth2/token"
    assert captured["data"]["grant_type"] == "urn:ietf:params:oauth:grant-type:token-exchange"
    assert captured["data"]["subject_token"] == "subject-tok"
    assert captured["data"]["subject_token_type"] == "urn:ietf:params:oauth:token-type:jwt"
    assert captured["data"]["actor_token"] == "actor-tok"
    assert captured["data"]["actor_token_type"] == "urn:ietf:params:oauth:token-type:jwt"
    assert captured["data"]["audience"] == "agentgateway"
    assert captured["headers"]["Authorization"] == "Bearer subject-tok"
