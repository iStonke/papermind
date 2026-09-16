"""ASGI admission/drain barrier, including already-running requests."""
from starlette.responses import JSONResponse

from app.services.maintenance import MaintenanceActive, acquire_write_activity


class WriteBarrierMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path", "").startswith("/health"):
            return await self.app(scope, receive, send)
        try:
            handle = acquire_write_activity()
        except MaintenanceActive:
            response = JSONResponse(
                {"error": {"message": "PaperMind sichert oder prüft gerade Daten. Bitte gleich erneut versuchen.",
                           "code": "maintenance_active"}},
                status_code=503, headers={"Retry-After": "5"},
            )
            return await response(scope, receive, send)

        async def guarded_send(message):
            # GET handlers can initialize settings/collections. Drain those,
            # but never pin maintenance behind an idle SSE or a PDF download.
            if message["type"] == "http.response.start" and scope["method"] in {"GET", "HEAD", "OPTIONS"}:
                handle.close()
            await send(message)

        try:
            await self.app(scope, receive, guarded_send)
        finally:
            handle.close()
