from app.routers.ai import router as ai_router
from app.routers.annotations import router as annotations_router
from app.routers.auth import router as auth_router
from app.routers.backup import router as backup_router
from app.routers.categories import router as categories_router
from app.routers.correspondents import router as correspondents_router
from app.routers.dashboard import router as dashboard_router
from app.routers.document_types import router as document_types_router
from app.routers.direct_upload import router as direct_upload_router
from app.routers.documents import router as documents_router
from app.routers.health import router as health_router
from app.routers.imports import router as import_router
from app.routers.jobs import router as jobs_router
from app.routers.retrieval import router as retrieval_router
from app.routers.retention import router as retention_router
from app.routers.saved_searches import router as saved_searches_router
from app.routers.scanners import router as scanners_router
from app.routers.settings import router as settings_router
from app.routers.sidebar import router as sidebar_router
from app.routers.smart_folders import router as smart_folders_router
from app.routers.system import router as system_router
from app.routers.tags import router as tags_router
from app.routers.users import router as users_router

__all__ = [
    "health_router",
    "auth_router",
    "users_router",
    "documents_router",
    "direct_upload_router",
    "import_router",
    "tags_router",
    "annotations_router",
    "categories_router",
    "correspondents_router",
    "dashboard_router",
    "document_types_router",
    "jobs_router",
    "retrieval_router",
    "retention_router",
    "saved_searches_router",
    "scanners_router",
    "smart_folders_router",
    "settings_router",
    "sidebar_router",
    "ai_router",
    "backup_router",
    "system_router",
]
