import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from dvm import auth, config

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJwks:   # stands in for the tenant's /.well-known/jwks.json
    def get_signing_key_from_jwt(self, token):
        return type("K", (), {"key": KEY.public_key()})()


@pytest.fixture(autouse=True)
def tenant(monkeypatch):
    monkeypatch.setattr(config, "AUTH0_AUDIENCE", "https://api.example")
    monkeypatch.setattr(auth, "ISSUER", "https://tenant.example/")
    monkeypatch.setattr(auth, "_jwks", FakeJwks())


def token(key=KEY, alg="RS256", **over):
    claims = {"sub": "auth0|1", "iss": "https://tenant.example/", "aud": "https://api.example", "exp": time.time() + 60}
    return jwt.encode({**claims, **over}, key, algorithm=alg)


def test_valid_token_passes():
    assert auth.verify(token())["sub"] == "auth0|1"


@pytest.mark.parametrize("bad", [
    token(aud="https://other.example"),
    token(iss="https://evil.example/"),
    token(exp=time.time() - 120),
    token(key=OTHER),                       # signed by someone else
    token(key="shared-secret", alg="HS256"),  # algorithm confusion
    "not-a-jwt",
])
def test_bad_tokens_are_refused(bad):
    with pytest.raises(jwt.PyJWTError):
        auth.verify(bad)
