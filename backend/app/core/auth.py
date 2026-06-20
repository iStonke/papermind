"""Authentication primitives for PaperMind.

Stdlib-only implementation (no external crypto dependencies):

* Password hashing via :func:`hashlib.scrypt` with a random per-password salt.
* Stateless, signed access tokens (HMAC-SHA256) carrying the user id and an
  expiry, encoded as ``<payload_b64>.<signature_b64>``.

Both pieces use :func:`hmac.compare_digest` for constant-time comparison.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid

# scrypt cost parameters. N must be a power of two; these are a reasonable
# balance for an interactive login on modest hardware (e.g. a Raspberry Pi).
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16

_HASH_PREFIX = "scrypt"


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def hash_password(password: str) -> str:
    """Return an encoded scrypt hash for ``password``.

    Format: ``scrypt$<N>$<r>$<p>$<salt_b64>$<hash_b64>``.
    """
    if not password:
        raise ValueError("password must not be empty")
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=0,
    )
    return f"{_HASH_PREFIX}${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verification of ``password`` against an encoded hash."""
    if not password or not encoded:
        return False
    try:
        prefix, n_str, r_str, p_str, salt_b64, hash_b64 = encoded.split("$")
        if prefix != _HASH_PREFIX:
            return False
        n, r, p = int(n_str), int(r_str), int(p_str)
        salt = _b64d(salt_b64)
        expected = _b64d(hash_b64)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=len(expected),
        maxmem=0,
    )
    return hmac.compare_digest(candidate, expected)


# --------------------------------------------------------------------------- #
# Access tokens (stateless, HMAC-signed)
# --------------------------------------------------------------------------- #
def _sign(payload_b64: str, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64e(signature)


def create_access_token(
    user_id: uuid.UUID | str,
    secret: str,
    ttl_seconds: int,
    *,
    scope: str = "session",
    session_version: int = 0,
    now: float | None = None,
) -> str:
    """Create a signed token embedding the user id, an absolute expiry and a scope.

    ``scope="session"`` is the normal login token (sent via Authorization header).
    ``scope="file"`` is a short-lived token used only for native resource loads
    (``<img>``/PDF/download URLs) where the token must travel in the query string.
    """
    if not secret:
        raise ValueError("token secret must not be empty")
    issued_at = int(now if now is not None else time.time())
    payload = {
        "sub": str(user_id),
        "scope": scope,
        "sv": int(session_version),
        "iat": issued_at,
        "exp": issued_at + int(ttl_seconds),
        "jti": secrets.token_hex(8),
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64, secret)}"


def decode_access_token(token: str, secret: str, *, now: float | None = None) -> dict | None:
    """Return the token payload if signature and expiry are valid, else ``None``."""
    if not token or not secret:
        return None
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None

    expected_sig = _sign(payload_b64, secret)
    if not hmac.compare_digest(signature, expected_sig):
        return None

    try:
        payload = json.loads(_b64d(payload_b64))
    except (ValueError, TypeError):
        return None

    exp = payload.get("exp")
    if not isinstance(exp, int):
        return None
    current = int(now if now is not None else time.time())
    if current >= exp:
        return None

    return payload
