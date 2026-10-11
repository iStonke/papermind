"""Authenticate multipart uploads before FastAPI starts parsing their body."""
import asyncio
from fastapi import HTTPException

from starlette.requests import Request
from starlette.responses import JSONResponse


def _authorized(scope) -> bool:
    from app.core.config import get_settings
    from app.core.deps import _has_valid_upload_key, _resolve_user, _UPLOAD_PREFIXES
    from app.db.session import AppSessionLocal
    if not get_settings().auth_enabled:
        return True
    request = Request(scope)
    if request.url.path.startswith(_UPLOAD_PREFIXES) and _has_valid_upload_key(request):
        return True
    with AppSessionLocal() as db:
        return _resolve_user(request, db) is not None


class UploadAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        if (scope["type"] == "http" and scope.get("path", "").startswith("/api/")
                and headers.get(b"content-type", b"").lower().startswith(b"multipart/form-data")):
            if not await asyncio.to_thread(_authorized, scope):
                response = JSONResponse({"error": {"code": "UNAUTHORIZED", "message": "Authentication required", "details": None}},
                    status_code=401, headers={"WWW-Authenticate": "Bearer"})
                return await response(scope, receive, send)
            from app.core.config import get_settings
            settings = get_settings()
            limit = max(settings.upload_request_max_bytes, settings.upload_max_bytes) + 1024 * 1024
            try:
                declared = int(headers.get(b"content-length", b"0"))
            except ValueError:
                declared = 0
            if declared > limit:
                response = JSONResponse({"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Upload request exceeds maximum allowed size", "details": None}}, status_code=413)
                return await response(scope, receive, send)
            total = 0
            original_receive = receive
            async def bounded_receive():
                nonlocal total
                message = await original_receive()
                total += len(message.get("body", b""))
                if total > limit:
                    raise HTTPException(413, "Upload request exceeds maximum allowed size")
                return message
            receive = bounded_receive
        await self.app(scope, receive, send)
