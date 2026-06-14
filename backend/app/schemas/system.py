"""Schemas für den System-/Hardware-Status (Raspberry Pi)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CpuStatus(BaseModel):
    usage_percent: float | None = None
    load_avg: list[float] | None = None  # 1, 5, 15 Minuten
    cores: int | None = None


class MemoryStatus(BaseModel):
    total_bytes: int | None = None
    used_bytes: int | None = None
    available_bytes: int | None = None
    used_percent: float | None = None
    swap_total_bytes: int | None = None
    swap_used_bytes: int | None = None


class DiskStatus(BaseModel):
    label: str
    path: str
    total_bytes: int | None = None
    used_bytes: int | None = None
    free_bytes: int | None = None
    used_percent: float | None = None


class TemperatureStatus(BaseModel):
    celsius: float | None = None
    label: str | None = None


class FanStatus(BaseModel):
    present: bool = False
    rpm: int | None = None
    level: int | None = None
    max_level: int | None = None
    active: bool | None = None


class HostInfo(BaseModel):
    model: str | None = None
    hostname: str | None = None
    os: str | None = None
    kernel: str | None = None
    uptime_seconds: float | None = None


class PowerInfo(BaseModel):
    available: bool = False
    pending: str | None = None  # aktuell eingereihte Aktion ("poweroff" / "reboot")


class SystemStatus(BaseModel):
    host: HostInfo
    cpu: CpuStatus
    memory: MemoryStatus
    temperature: TemperatureStatus
    fan: FanStatus
    disks: list[DiskStatus]
    power: PowerInfo
    collected_at: datetime


class ServiceActionInfo(BaseModel):
    action: Literal["check", "start", "stop", "restart"]
    label: str
    enabled: bool = False
    destructive: bool = False
    reason: str | None = None


class ServiceStatusItem(BaseModel):
    key: str
    label: str
    description: str
    status: Literal["ok", "warning", "error", "disabled", "unknown"]
    enabled: bool = True
    configurable: bool = False
    setting_key: str | None = None
    detail: str | None = None
    endpoint: str | None = None
    latency_ms: int | None = None
    checked_at: datetime
    actions: list[ServiceActionInfo] = Field(default_factory=list)


class ServiceStatusResponse(BaseModel):
    status: Literal["ok", "warning", "error", "unknown"]
    services: list[ServiceStatusItem]
    collected_at: datetime


class ServiceActionResponse(BaseModel):
    accepted: bool
    service_key: str
    action: str
    detail: str
    service: ServiceStatusItem | None = None


class PowerActionRequest(BaseModel):
    action: Literal["poweroff", "reboot"]


class PowerActionResponse(BaseModel):
    accepted: bool
    action: str
    detail: str
