from pydantic import BaseModel, Field


class SidebarImportsCounts(BaseModel):
    imported: int = 0
    processing: int = 0
    ready: int = 0
    failed: int = 0
    recent_total: int = 0


class SidebarCountsResponse(BaseModel):
    all_documents: int = 0
    untagged: int = 0
    unread_total: int = 0
    tags_total: int = 0
    imports: SidebarImportsCounts = Field(default_factory=SidebarImportsCounts)
    tags: dict[str, int] = Field(default_factory=dict)
    smart_folders: dict[str, int] = Field(default_factory=dict)
    saved_searches: dict[str, int] = Field(default_factory=dict)
