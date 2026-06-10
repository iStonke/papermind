import hmac
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Header, HTTPException, Request, status

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


def _client_identity(request: Request, api_key: str) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_host = forwarded_for.split(",", 1)[0].strip()
    if not client_host and request.client:
        client_host = request.client.host
    key_marker = api_key[:8] if api_key else "anonymous"
    return f"{client_host or 'unknown'}:{key_marker}"


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
