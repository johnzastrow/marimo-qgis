"""Bearer-token authentication for the bridge server.

A single high-entropy token is minted per server instance, handed to the
notebook subprocess via the MARIMO_QGIS_TOKEN environment variable, and required
on every HTTP request as `Authorization: Bearer <token>`.

Security notes:
- Token is generated with `secrets.token_urlsafe` (a CSPRNG), not `random`.
- Comparison uses `hmac.compare_digest` (constant-time) to avoid leaking the
  token through response timing.
- No token, wrong scheme, or wrong value -> caller must fail closed (HTTP 401).
"""

import hmac
import secrets

_SCHEME = "Bearer"


class TokenAuth:
    """Holds the session token and validates Authorization headers."""

    def __init__(self, token=None):
        # 32 bytes of CSPRNG entropy, URL-safe so it survives env/header round-trips.
        self.token = token or secrets.token_urlsafe(32)

    def authorize(self, header_value):
        """Return True iff `header_value` is `Bearer <valid-token>`.

        Args:
            header_value: the raw Authorization header (or None if absent).
        """
        if not header_value:
            return False
        parts = header_value.split(" ", 1)
        if len(parts) != 2 or parts[0] != _SCHEME:
            return False
        return hmac.compare_digest(parts[1].strip(), self.token)
