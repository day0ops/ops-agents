"""Solo STS token-exchange helper. Request shape verified live against the
running STS: form POST to /oauth2/token with jwt token types, audience, and
the subject token ALSO repeated as the Authorization header. The STS accepts
both Keycloak-issued and its own self-issued tokens as subject_token, which
is what makes the two-hop re-exchange chain work."""
import base64
import json

import requests

GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
JWT_TYPE = "urn:ietf:params:oauth:token-type:jwt"
DEFAULT_SA_TOKEN_PATH = "/var/run/secrets/tokens/sa-token"


def exchange(sts_base: str, subject_token: str, actor_token: str,
             audience: str = "agentgateway", timeout: int = 15) -> str:
    """Exchange subject_token (+ actor_token) at the STS, returning the
    exchanged access token. sts_base is scheme+host[:port] with no path."""
    resp = requests.post(
        sts_base.rstrip("/") + "/oauth2/token",
        data={
            "grant_type": GRANT,
            "subject_token": subject_token,
            "subject_token_type": JWT_TYPE,
            "actor_token": actor_token,
            "actor_token_type": JWT_TYPE,
            "audience": audience,
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Bearer " + subject_token,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def read_sa_token(path: str = DEFAULT_SA_TOKEN_PATH) -> str:
    """Read this agent's own projected Kubernetes ServiceAccount token."""
    with open(path) as f:
        return f.read().strip()


def decode_claims(token: str) -> dict:
    """Decode a JWT payload without verifying the signature - used only to
    surface the sub/act chain in responses, never for authorization."""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))
