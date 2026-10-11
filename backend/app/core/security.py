import hmac
import hashlib
import ipaddress
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Header, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings

settings = get_settings()

_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)

# Periodisches Aufräumen verhindert unbegrenztes Wachstum: Buckets ohne Treffer
# seit über einer Stunde (weit jenseits jedes Rate-Limit-Fensters von 300 s)
# werden entfernt. Der Sweep läuft höchstens alle 5 Minuten.
_last_sweep_at: float = 0.0
_SWEEP_INTERVAL_SECONDS = 300
_SWEEP_STALE_AFTER_SECONDS = 3600


def _sweep_rate_limit_buckets(now: float) -> None:
    global _last_sweep_at
    if now - _last_sweep_at < _SWEEP_INTERVAL_SECONDS:
        return
    _last_sweep_at = now
    stale_cutoff = now - _SWEEP_STALE_AFTER_SECONDS
    for key in list(_RATE_LIMIT_BUCKETS.keys()):
        hits = _RATE_LIMIT_BUCKETS[key]
        while hits and hits[0] <= stale_cutoff:
            hits.popleft()
        if not hits:
            del _RATE_LIMIT_BUCKETS[key]


def _extract_api_key(authorization: str | None, x_api_key: str | None = None) -> str:
    if x_api_key:
        return x_api_key.strip()

    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            return token.strip()

    return ""


def client_ip(request: Request) -> str:
    """Walk XFF from the trusted peer towards the first untrusted client."""
    peer = request.client.host if request.client else "unknown"
    networks = []
    for value in settings.auth_trusted_proxy_cidrs.split(","):
        if value.strip():
            try:
                networks.append(ipaddress.ip_network(value.strip(), strict=False))
            except ValueError:
                continue  # Invalid configuration must never extend trust.

    def trusted(address: str) -> bool:
        try:
            parsed = ipaddress.ip_address(address)
            return any(parsed in network for network in networks)
        except ValueError:
            return False

    if not trusted(peer):
        return peer
    for address in reversed(request.headers.get("x-forwarded-for", "").split(",")):
        address = address.strip()
        try:
            ipaddress.ip_address(address)
        except ValueError:
            return peer
        peer = address
        if not trusted(peer):
            break
    return peer


def _client_identity(request: Request, api_key: str) -> str:
    marker = hashlib.sha256(api_key.encode("utf-8")).hexdigest() if api_key else "anonymous"
    return f"{client_ip(request)}:{marker}"


def enforce_rate_limit(
    bucket: str,
    identity: str,
    *,
    limit: int,
    window_seconds: int,
    now_factory: Callable[[], float] = time.monotonic,
) -> None:
    now = now_factory()
    _sweep_rate_limit_buckets(now)
    cutoff = now - window_seconds
    key = f"{bucket}:{identity}"
    hits = _RATE_LIMIT_BUCKETS[key]

    while hits and hits[0] <= cutoff:
        hits.popleft()

    if len(hits) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many upload requests. Please try again later.",
        )

    hits.append(now)


def enforce_persistent_rate_limit(
    db: Session,
    bucket: str,
    identity: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    """Atomically enforce a rate limit in PostgreSQL.

    The identity is hashed before persistence so usernames and client addresses
    do not become readable operational data in the rate-limit table.
    """
    identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    key = f"{bucket}:{identity_hash}"
    row = db.execute(
        text(
            """
            INSERT INTO auth_rate_limits (key, window_started_at, hits, updated_at)
            VALUES (:key, now(), 1, now())
            ON CONFLICT (key) DO UPDATE SET
                hits = CASE
                    WHEN auth_rate_limits.window_started_at
                         <= now() - make_interval(secs => :window_seconds)
                    THEN 1
                    ELSE auth_rate_limits.hits + 1
                END,
                window_started_at = CASE
                    WHEN auth_rate_limits.window_started_at
                         <= now() - make_interval(secs => :window_seconds)
                    THEN now()
                    ELSE auth_rate_limits.window_started_at
                END,
                updated_at = now()
            RETURNING hits
            """
        ),
        {"key": key, "window_seconds": window_seconds},
    ).scalar_one()
    db.commit()
    if int(row) > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(window_seconds)},
        )


def verify_shared_upload_api_key(
    request: Request,
    authorization: str | None,
    x_api_key: str | None = None,
    *,
    service_name: str,
    rate_limit_bucket: str,
    rate_limit: int = 20,
    rate_limit_window_seconds: int = 300,
) -> None:
    configured_key = settings.direct_upload_api_key.strip()
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{service_name} is not configured.",
        )

    supplied_key = _extract_api_key(authorization, x_api_key)
    if not supplied_key or not hmac.compare_digest(supplied_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    enforce_rate_limit(
        rate_limit_bucket,
        _client_identity(request, supplied_key),
        limit=rate_limit,
        window_seconds=rate_limit_window_seconds,
    )
