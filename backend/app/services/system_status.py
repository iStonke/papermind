"""Erhebt Hardware-/Systemstatus eines Raspberry Pi (oder Linux-Hosts).

Das Backend läuft im Container, teilt sich aber den Kernel mit dem Host.
CPU/RAM/Load werden daher aus dem container-eigenen ``/proc`` gelesen
(spiegelt den Host). Temperatur, Lüfter und Geräteinfos kommen aus ``/sys``
bzw. dem Device-Tree, der Wurzel-Speicher aus dem (read-only) gemounteten
Host-Root. Fehlende Pfade werden tolerant mit ``None`` quittiert, damit die
Anzeige auch in Dev-Umgebungen ohne Mounts funktioniert.

Power-Aktionen (poweroff/reboot) kann ein Container nicht selbst ausführen.
Statt dessen wird eine Kommando-Datei in ein geteiltes Verzeichnis geschrieben,
das ein kleiner Host-Helfer (systemd-Service, siehe ``deploy/host-control``)
überwacht und ausführt.
"""

from __future__ import annotations

import asyncio
import glob
import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.schemas.system import (
    CpuStatus,
    DiskStatus,
    FanStatus,
    HostInfo,
    MemoryStatus,
    PowerInfo,
    SystemStatus,
    TemperatureStatus,
)

settings = get_settings()

# Vom Host-Helfer gelesene Kommando-Datei.
_COMMAND_FILENAME = "command"
_VALID_ACTIONS = ("poweroff", "reboot")


def _read_text(path: str | Path) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _read_first_line(path: str | Path) -> str | None:
    text = _read_text(path)
    if text is None:
        return None
    return text.splitlines()[0].strip() if text.strip() else None


def _resolve_base(configured: str, fallback: str) -> str:
    """Bevorzugt den konfigurierten (gemounteten) Pfad, fällt sonst zurück."""
    if configured and os.path.isdir(configured):
        return configured
    return fallback


def _sys_path(*parts: str) -> str:
    base = _resolve_base(settings.system_sys_path, "/sys")
    return os.path.join(base, *parts)


def _host_root() -> str:
    return _resolve_base(settings.system_host_root, "/")


# ── CPU ───────────────────────────────────────────────────────────────────────

def _read_cpu_times() -> tuple[int, int] | None:
    """Liest die aggregierte CPU-Zeile aus /proc/stat -> (idle, total)."""
    text = _read_text("/proc/stat")
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("cpu "):
            parts = [int(x) for x in line.split()[1:] if x.isdigit()]
            if len(parts) < 4:
                return None
            idle = parts[3] + (parts[4] if len(parts) > 4 else 0)  # idle + iowait
            total = sum(parts)
            return idle, total
    return None


async def _collect_cpu() -> CpuStatus:
    status = CpuStatus(cores=os.cpu_count())

    loadavg = _read_first_line("/proc/loadavg")
    if loadavg:
        try:
            status.load_avg = [float(x) for x in loadavg.split()[:3]]
        except ValueError:
            status.load_avg = None

    first = _read_cpu_times()
    if first:
        await asyncio.sleep(0.18)
        second = _read_cpu_times()
        if second:
            idle_delta = second[0] - first[0]
            total_delta = second[1] - first[1]
            if total_delta > 0:
                usage = (1.0 - idle_delta / total_delta) * 100.0
                status.usage_percent = round(max(0.0, min(100.0, usage)), 1)
    return status


# ── Memory ──────────────────────────────────────────────────────────────────

def _collect_memory() -> MemoryStatus:
    status = MemoryStatus()
    text = _read_text("/proc/meminfo")
    if not text:
        return status

    values: dict[str, int] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        rest = rest.strip()
        if not rest:
            continue
        num = rest.split()[0]
        if num.isdigit():
            values[key] = int(num) * 1024  # kB -> bytes

    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if total:
        status.total_bytes = total
        if available is not None:
            status.available_bytes = available
            status.used_bytes = total - available
            status.used_percent = round((total - available) / total * 100.0, 1)

    swap_total = values.get("SwapTotal")
    swap_free = values.get("SwapFree")
    if swap_total is not None:
        status.swap_total_bytes = swap_total
        if swap_free is not None:
            status.swap_used_bytes = swap_total - swap_free
    return status


# ── Disk ──────────────────────────────────────────────────────────────────

def _disk_for(label: str, path: str) -> DiskStatus | None:
    try:
        st = os.statvfs(path)
    except OSError:
        return None
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - st.f_bfree * st.f_frsize
    status = DiskStatus(label=label, path=path, total_bytes=total, free_bytes=free, used_bytes=used)
    if total > 0:
        status.used_percent = round(used / total * 100.0, 1)
    return status


def _collect_disks() -> list[DiskStatus]:
    disks: list[DiskStatus] = []
    root = _disk_for("System", _host_root())
    if root:
        disks.append(root)
    # Dokumentspeicher (PDF-Volume) – nur ergänzen, wenn anderes Gerät.
    storage = _disk_for("Dokumente", settings.storage_path)
    if storage and not any(d.path == storage.path for d in disks):
        disks.append(storage)
    return disks


# ── Temperatur ──────────────────────────────────────────────────────────────

def _collect_temperature() -> TemperatureStatus:
    status = TemperatureStatus()
    zones = sorted(glob.glob(_sys_path("class", "thermal", "thermal_zone*")))
    best: float | None = None
    label: str | None = None
    for zone in zones:
        raw = _read_first_line(os.path.join(zone, "temp"))
        if not raw or not raw.lstrip("-").isdigit():
            continue
        celsius = int(raw) / 1000.0
        if best is None or celsius > best:
            best = celsius
            label = _read_first_line(os.path.join(zone, "type"))
    if best is not None:
        status.celsius = round(best, 1)
        status.label = label
    return status


# ── Lüfter ───────────────────────────────────────────────────────────────────

def _collect_fan() -> FanStatus:
    status = FanStatus()

    # 1) Echte Drehzahl (Pi 5 offizieller Lüfter / generische hwmon-Geräte).
    rpm_candidates = (
        glob.glob(_sys_path("devices", "platform", "cooling_fan", "hwmon", "hwmon*", "fan1_input"))
        + glob.glob(_sys_path("class", "hwmon", "hwmon*", "fan1_input"))
    )
    for path in rpm_candidates:
        raw = _read_first_line(path)
        if raw and raw.isdigit():
            status.present = True
            status.rpm = int(raw)
            status.active = status.rpm > 0
            break

    # 2) PWM-/Kühlstufe (thermal cooling_device, oft der Lüfter am Pi).
    for dev in sorted(glob.glob(_sys_path("class", "thermal", "cooling_device*"))):
        dtype = _read_first_line(os.path.join(dev, "type")) or ""
        if "fan" not in dtype.lower():
            continue
        cur = _read_first_line(os.path.join(dev, "cur_state"))
        mx = _read_first_line(os.path.join(dev, "max_state"))
        if cur is not None and cur.isdigit():
            status.present = True
            status.level = int(cur)
            if status.active is None:
                status.active = status.level > 0
        if mx is not None and mx.isdigit():
            status.max_level = int(mx)
        break

    return status


# ── Host-Infos ───────────────────────────────────────────────────────────────

def _collect_host() -> HostInfo:
    info = HostInfo()

    model = _read_text(_sys_path("firmware", "devicetree", "base", "model")) or _read_text(
        "/proc/device-tree/model"
    )
    if model:
        info.model = model.replace("\x00", "").strip() or None

    uptime = _read_first_line("/proc/uptime")
    if uptime:
        try:
            info.uptime_seconds = float(uptime.split()[0])
        except ValueError:
            info.uptime_seconds = None

    kernel = _read_first_line("/proc/sys/kernel/osrelease")
    if kernel:
        info.kernel = kernel

    host_root = _host_root()
    hostname = _read_first_line(os.path.join(host_root, "etc", "hostname"))
    if hostname:
        info.hostname = hostname

    os_release = _read_text(os.path.join(host_root, "etc", "os-release"))
    if os_release:
        for line in os_release.splitlines():
            if line.startswith("PRETTY_NAME="):
                info.os = line.split("=", 1)[1].strip().strip('"') or None
                break

    return info


# ── Power ────────────────────────────────────────────────────────────────────

def _command_path() -> str | None:
    directory = settings.host_control_dir.strip()
    if not directory:
        return None
    return os.path.join(directory, _COMMAND_FILENAME)


def _power_available() -> bool:
    directory = settings.host_control_dir.strip()
    return bool(directory) and os.path.isdir(directory)


def _pending_action() -> str | None:
    path = _command_path()
    if not path:
        return None
    line = _read_first_line(path)
    if not line:
        return None
    action = line.split()[0]
    if action in _VALID_ACTIONS:
        return action
    return None


def _collect_power() -> PowerInfo:
    return PowerInfo(available=_power_available(), pending=_pending_action())


def request_power_action(action: str) -> tuple[bool, str]:
    """Reiht eine Power-Aktion für den Host-Helfer ein.

    Returns (accepted, detail).
    """
    if action not in _VALID_ACTIONS:
        return False, f"Unbekannte Aktion: {action}"
    path = _command_path()
    if not path or not _power_available():
        return False, (
            "Power-Aktionen sind nicht eingerichtet. Bitte den Host-Helfer "
            "konfigurieren (HOST_CONTROL_DIR + deploy/host-control)."
        )
    pending = _pending_action()
    if pending:
        return False, f"Es ist bereits eine Aktion eingereiht: {pending}."
    payload = f"{action} {datetime.now(timezone.utc).isoformat()}\n"
    try:
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except OSError as exc:
        return False, f"Kommando konnte nicht geschrieben werden: {exc}"
    label = "Herunterfahren" if action == "poweroff" else "Neustart"
    return True, f"{label} wurde eingereiht und wird in Kürze ausgeführt."


# ── Aggregation ──────────────────────────────────────────────────────────────

async def collect_status() -> SystemStatus:
    cpu = await _collect_cpu()
    return SystemStatus(
        host=_collect_host(),
        cpu=cpu,
        memory=_collect_memory(),
        temperature=_collect_temperature(),
        fan=_collect_fan(),
        disks=_collect_disks(),
        power=_collect_power(),
        collected_at=datetime.now(timezone.utc),
    )
