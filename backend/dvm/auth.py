"""Auth0 access-token validation: RS256 against the tenant's JWKS, checking signature, expiry, issuer and audience."""
from __future__ import annotations

import asyncio
import logging

import jwt

from dvm import config

log = logging.getLogger(__name__)

ENABLED = bool(config.AUTH0_DOMAIN and config.AUTH0_AUDIENCE)
ISSUER = config.AUTH0_ISSUER or f"https://{config.AUTH0_DOMAIN}/"
_jwks = jwt.PyJWKClient(f"https://{config.AUTH0_DOMAIN}/.well-known/jwks.json", cache_keys=True) if ENABLED else None


def verify(token: str) -> dict:
    """Claims of a valid access token. Raises jwt.PyJWTError (including JWKS fetch failures) otherwise."""
    key = _jwks.get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["RS256"], audience=config.AUTH0_AUDIENCE, issuer=ISSUER,
                      options={"require": ["exp", "iss", "aud", "sub"]})


async def verify_async(token: str) -> dict:
    return await asyncio.to_thread(verify, token)   # the JWKS fetch is blocking; it's cached after the first call
