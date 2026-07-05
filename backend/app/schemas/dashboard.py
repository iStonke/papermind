from pydantic import BaseModel, Field


class DashboardStats(BaseModel):
    documents_total: int = 0
    this_month: int = 0
    correspondents: int = 0
    tags: int = 0
    document_types: int = 0
    storage_bytes: int = 0
    storage_limit_bytes: int | None = None
    # Trend-Deltas
    total_trend_pct: float | None = None
    correspondents_new: int = 0
    untagged_pct: float = 0.0


class DashboardMonthPoint(BaseModel):
    month: str  # ISO "YYYY-MM"
    count: int = 0


class DashboardYearPoint(BaseModel):
    year: int
    count: int = 0


class DashboardCorrespondent(BaseModel):
    name: str
    count: int = 0


class DashboardTagShare(BaseModel):
    tag: str
    count: int = 0


class DashboardTypeShare(BaseModel):
    type: str
    count: int = 0


class DashboardSearchTerm(BaseModel):
    term: str
    count: int = 0


class DashboardStoragePoint(BaseModel):
    month: str  # ISO "YYYY-MM"
    bytes: int = 0  # kumuliert bis Ende dieses Monats


class DashboardAttention(BaseModel):
    unread: int = 0
    untagged: int = 0
    retention_due: int = 0
    to_review: int = 0
    unclassified: int = 0
    ocr_issues: int = 0
    without_document_type: int = 0


class DashboardRecentItem(BaseModel):
    id: str
    title: str
    correspondent: str | None = None
    date: str | None = None  # ISO date/datetime


class DashboardOverviewResponse(BaseModel):
    stats: DashboardStats = Field(default_factory=DashboardStats)
    documents_per_month: list[DashboardMonthPoint] = Field(default_factory=list)
    documents_per_month_total: int = 0
    documents_per_year: list[DashboardYearPoint] = Field(default_factory=list)
    top_correspondents: list[DashboardCorrespondent] = Field(default_factory=list)
    tag_distribution: list[DashboardTagShare] = Field(default_factory=list)
    tag_count_total: int = 0
    type_distribution: list[DashboardTypeShare] = Field(default_factory=list)
    type_count_total: int = 0
    storage_series: list[DashboardStoragePoint] = Field(default_factory=list)
    top_searches: list[DashboardSearchTerm] = Field(default_factory=list)
    attention: DashboardAttention = Field(default_factory=DashboardAttention)
    recent: list[DashboardRecentItem] = Field(default_factory=list)
