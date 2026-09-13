from __future__ import annotations

"""OAuth 2.1 resource-server token verification for the integrated MCP service."""

import asyncio
from typing import Iterable, Mapping

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken


def _scopes(claims: Mapping[str, object]) -> list[str]:
    raw_scope = claims.get("scope", "")
    values = set(str(raw_scope).split()) if isinstance(raw_scope, str) else set()
    permissions = claims.get("permissions", [])
    if isinstance(permissions, Iterable) and not isinstance(permissions, (str, bytes)):
        values.update(str(item) for item in permissions)
    return sorted(value for value in values if value)


class OIDCJWTVerifier:
    """Validate signed OIDC access tokens against issuer, audience and JWKS."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        jwk_client: PyJWKClient | None = None,
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.jwk_client = jwk_client or PyJWKClient(jwks_url, cache_keys=True)

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            signing_key = await asyncio.to_thread(
                self.jwk_client.get_signing_key_from_jwt,
                token,
            )
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except (jwt.PyJWTError, ValueError, OSError):
            return None
        if not isinstance(claims, dict):
            return None
        subject = claims.get("sub")
        client_id = claims.get("azp") or claims.get("client_id") or subject
        expires_at = claims.get("exp")
        if not isinstance(subject, str) or not isinstance(client_id, str):
            return None
        if not isinstance(expires_at, int):
            return None
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=_scopes(claims),
            expires_at=expires_at,
            resource=self.audience,
            subject=subject,
            claims=dict(claims),
        )


__all__ = ["OIDCJWTVerifier"]
