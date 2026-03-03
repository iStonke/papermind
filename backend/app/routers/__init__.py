from app.routers.ai import router as ai_router
from app.routers.documents import router as documents_router
from app.routers.health import router as health_router
from app.routers.imports import router as import_router
from app.routers.jobs import router as jobs_router
from app.routers.mobile_upload import router as mobile_upload_router
from app.routers.retrieval import router as retrieval_router
from app.routers.saved_searches import router as saved_searches_router
from app.routers.settings import router as settings_router
from app.routers.sidebar import router as sidebar_router
from app.routers.smart_folders import router as smart_folders_router
from app.routers.tags import router as tags_router

__all__ = [
    "health_router",
    "documents_router",
    "import_router",
    "tags_router",
    "jobs_router",
    "mobile_upload_router",
    "retrieval_router",
    "saved_searches_router",
    "smart_folders_router",
    "settings_router",
    "sidebar_router",
    "ai_router",
]
