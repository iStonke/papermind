import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.scanner import ScannerDevice, ScannerDeviceRecipient, ScannerScanCommand, ScannerScanJob
from app.models.user import User
from app.schemas.auth import UserRead
from app.schemas.scanners import (
    ScanCommand,
    ScanCommandResponse,
    ScannerDeviceCreateRequest,
    ScannerDeviceListResponse,
    ScannerDeviceRead,
    ScannerDeviceUpdateRequest,
)
from app.services.utils import is_unique_violation


SCAN_STATUS_STALE_SECONDS = 30
# Eingereihte Befehle, die der Worker länger nicht abholen konnte (z. B. Host-
# Poller war aus), gelten als veraltet und werden verworfen statt verspätet zu
# feuern - ein Scan soll nur kurz nach dem Klick passieren, nie Minuten später.
SCAN_COMMAND_EXPIRY_SECONDS = 90
SCAN_JOB_ACTIVE_STATES = ("queued", "scanning", "processing")
SCAN_JOB_TERMINAL_STATES = ("ready", "error")

# Strukturierte Fehlerarten (scanner_scan_jobs.error_kind), damit die UI gezielt
# erklären kann, was schiefging.
SCAN_ERROR_TIMEOUT = "timeout"
SCAN_ERROR_FILE_MISSING = "file_missing"
SCAN_ERROR_SCANNER_OFFLINE = "scanner_offline"
SCAN_ERROR_FAILED = "failed"

# Ein aktiver Job, der so lange nicht mehr fortgeschritten ist, gilt als
# hängengeblieben und wird auf "error/timeout" gesetzt - sonst zeigt die UI ewig
# "Scanne...". Die Frist hängt vom Zustand ab, damit eine LEGITIME Pause zwischen
# zwei Seiten einer Mehrseiten-Folge (Job wartet dann in "processing") nicht
# fälschlich als Fehler auflauft, ein wirklich abgebrochener Scan (Job klebt in
# "scanning", z. B. USB-Disconnect mitten im Lauf) aber zügig erkannt wird:
#   scanning   - aktiver Scan; ein Blatt dauert Sekunden, >3 min = tot
#   queued     - vom Worker dispatcht, aber der Host meldet kein "scanning"
#   processing - Scan fertig, wartet auf nächste Seite/Abschluss -> großzügig
# (Der Host-Idle-Timer schließt einen vergessenen Batch ohnehin selbst ab.)
SCAN_JOB_STALE_TIMEOUTS = {
    "scanning": 180,
    "queued": 180,
    "processing": 1800,
}

# Abgeschlossene Jobs (ready/error) werden nach dieser Frist gelöscht, damit die
# Tabelle nicht unbegrenzt wächst. Der UI-Status lebt ohnehin nur kurz.
SCAN_JOB_RETENTION_SECONDS = 7 * 24 * 3600


def normalize_scanner_device_key(raw: str | None) -> str:
    return " ".join(str(raw or "").split()).strip()


def is_scanning_active(scanner: ScannerDevice) -> bool:
    """True, wenn der Host kürzlich "scanning" gemeldet hat.

    Das Staleness-Fenster fängt den Fall ab, dass der Host mittendrin
    abstürzt (z. B. USB-Disconnect) und kein "fertig"-Status mehr
    geschrieben wird - sonst würde die UI dauerhaft "Scanne..." anzeigen.
    """
    if scanner.scanning_since is None:
        return False
    age = (datetime.now(timezone.utc) - scanner.scanning_since).total_seconds()
    return age < SCAN_STATUS_STALE_SECONDS


class ScannerService:
    def __init__(self, db: Session):
        self.db = db

    def _recipients_for(self, scanner_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[UserRead]]:
        if not scanner_ids:
            return {}
        rows = self.db.execute(
            select(ScannerDeviceRecipient.scanner_device_id, User)
            .join(User, User.id == ScannerDeviceRecipient.user_id)
            .where(ScannerDeviceRecipient.scanner_device_id.in_(scanner_ids))
            .order_by(func.lower(User.username).asc(), User.created_at.asc())
        ).all()
        result: dict[uuid.UUID, list[UserRead]] = {scanner_id: [] for scanner_id in scanner_ids}
        for scanner_id, user in rows:
            result.setdefault(scanner_id, []).append(UserRead.model_validate(user, from_attributes=True))
        return result

    def _read(self, scanner: ScannerDevice, recipients: list[UserRead] | None = None) -> ScannerDeviceRead:
        return ScannerDeviceRead(
            id=scanner.id,
            device_key=scanner.device_key,
            name=scanner.name,
            enabled=scanner.enabled,
            live_page_mode=scanner.live_page_mode,
            created_at=scanner.created_at,
            updated_at=scanner.updated_at,
            last_seen_at=scanner.last_seen_at,
            recipients=recipients or [],
        )

    def list_devices(self) -> ScannerDeviceListResponse:
        scanners = list(
            self.db.scalars(select(ScannerDevice).order_by(func.lower(ScannerDevice.name).asc())).all()
        )
        recipients = self._recipients_for([scanner.id for scanner in scanners])
        return ScannerDeviceListResponse(
            items=[self._read(scanner, recipients.get(scanner.id, [])) for scanner in scanners]
        )

    def get_by_key(self, device_key: str) -> ScannerDevice | None:
        normalized = normalize_scanner_device_key(device_key)
        if not normalized:
            return None
        return self.db.scalar(select(ScannerDevice).where(ScannerDevice.device_key == normalized))

    def set_scanning_state(self, device_key: str, scanning_since: datetime | None) -> None:
        scanner = self.get_by_key(device_key)
        if scanner is None:
            return
        if scanner.scanning_since == scanning_since:
            return
        previous_active = is_scanning_active(scanner)
        scanner.scanning_since = scanning_since
        next_active = scanning_since is not None
        now = datetime.now(timezone.utc)
        if next_active and not previous_active:
            self.mark_scan_started(scanner.id, started_at=scanning_since or now)
        elif previous_active and not next_active:
            self.mark_scan_processing(scanner.id, finished_at=now)
        self.db.commit()

    def get_or_create_for_worker(self, device_key: str, *, name: str | None = None) -> ScannerDevice:
        normalized_key = normalize_scanner_device_key(device_key)
        display_name = normalize_scanner_device_key(name) or normalized_key
        scanner = self.get_by_key(normalized_key)
        now = datetime.now(timezone.utc)
        if scanner is not None:
            scanner.last_seen_at = now
            scanner.updated_at = now
            self.db.flush()
            return scanner

        scanner = ScannerDevice(
            device_key=normalized_key,
            name=display_name,
            enabled=True,
            last_seen_at=now,
        )
        self.db.add(scanner)
        self.db.flush()
        return scanner

    def enqueue_scan_command(
        self,
        scanner_id: uuid.UUID,
        command: ScanCommand,
        *,
        requested_by: uuid.UUID | None = None,
    ) -> ScanCommandResponse:
        """Reiht einen UI-Scan-Befehl ein, den der Worker an den Host weiterreicht."""
        scanner = self.db.get(ScannerDevice, scanner_id)
        if scanner is None:
            raise NotFoundError("Scanner device not found", details={"scanner_id": str(scanner_id)})
        if not scanner.enabled:
            raise BadRequestError("Scanner is disabled", details={"scanner_id": str(scanner_id)})

        job = ScannerScanJob(
            scanner_device_id=scanner.id,
            command=command,
            requested_by_user_id=requested_by,
            state="queued",
        )
        self.db.add(job)
        self.db.flush()  # job.id für die Befehlsverknüpfung benötigt
        entry = ScannerScanCommand(
            scanner_device_id=scanner.id,
            command=command,
            requested_by_user_id=requested_by,
            scan_job_id=job.id,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return ScanCommandResponse(id=entry.id, command=command, created_at=entry.created_at)

    def _job_for_update(self, job_id: uuid.UUID, states: tuple[str, ...]) -> ScannerScanJob | None:
        """Genau diesen Job laden, wenn er noch in einem der Zustände ist.

        Für die exakte Zuordnung Hardwarelauf → Backend-Job (Job-ID kommt über
        die Befehlsdatei/den Dateinamen vom Host zurück)."""
        return self.db.scalars(
            select(ScannerScanJob)
            .where(ScannerScanJob.id == job_id)
            .where(ScannerScanJob.state.in_(states))
            .with_for_update(skip_locked=True)
        ).first()

    def _latest_active_job(self, scanner_id: uuid.UUID, states: tuple[str, ...] = SCAN_JOB_ACTIVE_STATES) -> ScannerScanJob | None:
        return self.db.scalars(
            select(ScannerScanJob)
            .where(ScannerScanJob.scanner_device_id == scanner_id)
            .where(ScannerScanJob.import_inbox_item_id.is_(None))
            .where(ScannerScanJob.state.in_(states))
            .order_by(ScannerScanJob.created_at.asc())
            .with_for_update(skip_locked=True)
        ).first()

    def mark_scan_started(self, scanner_id: uuid.UUID, *, started_at: datetime | None = None) -> ScannerScanJob:
        now = datetime.now(timezone.utc)
        job = self._latest_active_job(scanner_id, ("queued", "processing"))
        if job is None:
            job = ScannerScanJob(
                scanner_device_id=scanner_id,
                command="hardware",
                state="scanning",
                started_at=started_at or now,
            )
            self.db.add(job)
        else:
            job.state = "scanning"
            job.started_at = job.started_at or started_at or now
            job.error = None
        job.updated_at = now
        return job

    def mark_scan_processing(self, scanner_id: uuid.UUID, *, finished_at: datetime | None = None) -> ScannerScanJob | None:
        now = datetime.now(timezone.utc)
        job = self._latest_active_job(scanner_id, ("scanning", "queued"))
        if job is None:
            return None
        job.state = "processing"
        job.finished_at = finished_at or now
        job.updated_at = now
        return job

    def mark_scan_ready(
        self,
        scanner_id: uuid.UUID,
        *,
        import_inbox_item_id: uuid.UUID,
        source_file_id: uuid.UUID,
        page_count: int,
        job_id: uuid.UUID | None = None,
    ) -> ScannerScanJob:
        now = datetime.now(timezone.utc)
        # Exakte Zuordnung bevorzugen: Kam die Job-ID über den Dateinamen vom
        # Host zurück und der Job ist noch aktiv, genau den abschließen. Sonst
        # auf den ältesten aktiven Job des Scanners zurückfallen (Hardwaretasten
        # ohne UI-Auslösung haben keine Job-ID).
        job = None
        if job_id is not None:
            job = self._job_for_update(job_id, SCAN_JOB_ACTIVE_STATES)
        if job is None:
            job = self._latest_active_job(scanner_id, ("processing", "scanning", "queued"))
        if job is None:
            job = ScannerScanJob(
                scanner_device_id=scanner_id,
                command="hardware",
                created_at=now,
            )
            self.db.add(job)
        job.state = "ready"
        job.import_inbox_item_id = import_inbox_item_id
        job.source_file_id = source_file_id
        job.page_count = max(0, int(page_count or 0))
        job.finished_at = job.finished_at or now
        job.updated_at = now
        job.error = None
        job.error_kind = None
        # Auf einem Einzel-Flachbett laufen Scans seriell - ein fertig
        # produzierter Beleg schließt die gesamte Session ab. Übrige aktive Jobs
        # desselben Scanners sind Zwischenschritte derselben Mehrseiten-Folge
        # (mehrere "page"- plus "finish"-Befehle) und damit gegenstandslos. Sie
        # werden entfernt, sonst liefen sie später fälschlich als Timeout auf.
        self.db.flush()  # neu angelegten Job-Datensatz mit id versehen
        self.db.execute(
            delete(ScannerScanJob)
            .where(ScannerScanJob.scanner_device_id == scanner_id)
            .where(ScannerScanJob.id != job.id)
            .where(ScannerScanJob.state.in_(SCAN_JOB_ACTIVE_STATES))
        )
        return job

    def fail_scan_job(
        self,
        *,
        scanner_id: uuid.UUID | None = None,
        error_kind: str,
        message: str,
        job_id: uuid.UUID | None = None,
        commit: bool = False,
    ) -> ScannerScanJob | None:
        """Setzt einen aktiven Job auf "error" mit strukturierter Fehlerart.

        Trifft den über ``job_id`` benannten Job (exakte Zuordnung) oder - als
        Fallback - den ältesten aktiven Job von ``scanner_id``. Existiert kein
        aktiver Job, passiert nichts (None) - ein Fehler ohne zugehörigen Lauf
        muss nicht künstlich erzeugt werden."""
        now = datetime.now(timezone.utc)
        job = None
        if job_id is not None:
            job = self._job_for_update(job_id, SCAN_JOB_ACTIVE_STATES)
        if job is None and scanner_id is not None:
            job = self._latest_active_job(scanner_id, SCAN_JOB_ACTIVE_STATES)
        if job is None:
            return None
        job.state = "error"
        job.error_kind = error_kind
        job.error = str(message or "Scan fehlgeschlagen.")[:500]
        job.finished_at = job.finished_at or now
        job.updated_at = now
        if commit:
            self.db.commit()
        return job

    def expire_stale_scan_jobs(self, *, timeout_seconds: int | None = None) -> int:
        """Hängengebliebene aktive Jobs auf error/timeout setzen.

        Fängt den Fall ab, dass der Host mitten im Lauf abbricht (USB-Disconnect,
        Skriptfehler) und nie ein Folge-Status kommt - sonst zeigt die UI ewig
        "Scanne...". Die Frist ist je Zustand unterschiedlich (siehe
        SCAN_JOB_STALE_TIMEOUTS), damit eine legitime Pause zwischen zwei Seiten
        nicht fälschlich als Fehler gilt. ``timeout_seconds`` überschreibt die
        Frist für ALLE Zustände einheitlich (v. a. für Tests).

        Gibt die Anzahl umgesetzter Jobs zurück."""
        now = datetime.now(timezone.utc)
        if timeout_seconds is not None:
            thresholds = {state: max(1, int(timeout_seconds)) for state in SCAN_JOB_ACTIVE_STATES}
        else:
            thresholds = SCAN_JOB_STALE_TIMEOUTS
        # Kandidaten grob über die kürzeste Frist vorfiltern, dann je Zustand
        # genau prüfen (aktive Jobs sind ohnehin wenige auf einem Einzel-Pi).
        min_threshold = min(thresholds.values())
        candidates = list(
            self.db.scalars(
                select(ScannerScanJob)
                .where(ScannerScanJob.state.in_(SCAN_JOB_ACTIVE_STATES))
                .where(ScannerScanJob.updated_at < now - timedelta(seconds=min_threshold))
                .with_for_update(skip_locked=True)
            ).all()
        )
        expired = 0
        for job in candidates:
            threshold = thresholds.get(job.state)
            if threshold is None:
                continue
            if (now - job.updated_at).total_seconds() < threshold:
                continue
            job.state = "error"
            job.error_kind = SCAN_ERROR_TIMEOUT
            job.error = "Der Scanvorgang hat das Zeitlimit überschritten."
            job.finished_at = job.finished_at or now
            job.updated_at = now
            expired += 1
        if expired:
            self.db.commit()
        return expired

    def cleanup_old_scan_jobs(self, *, retention_seconds: int = SCAN_JOB_RETENTION_SECONDS) -> int:
        """Abgeschlossene Jobs (ready/error) nach Ablauf der Frist löschen."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(60, int(retention_seconds)))
        result = self.db.execute(
            delete(ScannerScanJob)
            .where(ScannerScanJob.state.in_(SCAN_JOB_TERMINAL_STATES))
            .where(ScannerScanJob.finished_at.is_not(None))
            .where(ScannerScanJob.finished_at < cutoff)
        )
        self.db.commit()
        return int(result.rowcount or 0)

    def claim_pending_scan_commands(self, scanner_id: uuid.UUID) -> list[tuple[ScanCommand, uuid.UUID | None]]:
        """Holt offene Befehle eines Scanners FIFO und markiert sie als konsumiert.

        Wird vom Worker im Sync-Tick aufgerufen. Veraltete Befehle (siehe
        SCAN_COMMAND_EXPIRY_SECONDS) werden als konsumiert markiert, aber nicht
        zurückgegeben - so feuert ein lange liegengebliebener Klick nicht mehr.
        Ein abgelaufener Befehl bedeutet, dass der Host-Poller offline war: der
        zugehörige Job wird dann als ``scanner_offline`` markiert, statt still in
        "queued" zu versanden.

        Gibt je gültigem Befehl ein Tupel (command, scan_job_id) zurück. Die
        Job-ID reicht der Worker an den Host weiter, damit der Hardwarelauf
        später exakt diesem Job zugeordnet werden kann.
        """
        rows = list(
            self.db.scalars(
                select(ScannerScanCommand)
                .where(
                    ScannerScanCommand.consumed_at.is_(None),
                    ScannerScanCommand.scanner_device_id == scanner_id,
                )
                .order_by(ScannerScanCommand.created_at.asc())
                .with_for_update(skip_locked=True)
            ).all()
        )
        if not rows:
            return []

        now = datetime.now(timezone.utc)
        claimed: list[tuple[ScanCommand, uuid.UUID | None]] = []
        for row in rows:
            row.consumed_at = now
            age = (now - row.created_at).total_seconds()
            if age <= SCAN_COMMAND_EXPIRY_SECONDS:
                claimed.append((row.command, row.scan_job_id))  # type: ignore[arg-type]
            elif row.scan_job_id is not None:
                self.fail_scan_job(
                    scanner_id=scanner_id,
                    job_id=row.scan_job_id,
                    error_kind=SCAN_ERROR_SCANNER_OFFLINE,
                    message="Der Scanner war nicht erreichbar (Befehl abgelaufen).",
                )
        self.db.commit()
        return claimed

    def _set_recipients(self, scanner_id: uuid.UUID, user_ids: list[uuid.UUID]) -> None:
        normalized_ids = []
        seen = set()
        for user_id in user_ids:
            if user_id in seen:
                continue
            seen.add(user_id)
            normalized_ids.append(user_id)

        if normalized_ids:
            active_count = self.db.scalar(
                select(func.count(User.id)).where(User.id.in_(normalized_ids), User.is_active.is_(True))
            )
            if int(active_count or 0) != len(normalized_ids):
                raise NotFoundError("One or more scanner recipient users were not found")

        self.db.execute(delete(ScannerDeviceRecipient).where(ScannerDeviceRecipient.scanner_device_id == scanner_id))
        for user_id in normalized_ids:
            self.db.add(ScannerDeviceRecipient(scanner_device_id=scanner_id, user_id=user_id))

    def create_device(self, payload: ScannerDeviceCreateRequest) -> ScannerDeviceRead:
        scanner = ScannerDevice(
            device_key=normalize_scanner_device_key(payload.device_key),
            name=normalize_scanner_device_key(payload.name),
            enabled=payload.enabled,
        )
        self.db.add(scanner)
        try:
            self.db.flush()
            self._set_recipients(scanner.id, payload.recipient_user_ids)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Scanner device key already exists", details={"device_key": payload.device_key}) from exc
            raise
        self.db.refresh(scanner)
        recipients = self._recipients_for([scanner.id]).get(scanner.id, [])
        return self._read(scanner, recipients)

    def update_device(self, scanner_id: uuid.UUID, payload: ScannerDeviceUpdateRequest) -> ScannerDeviceRead:
        scanner = self.db.get(ScannerDevice, scanner_id)
        if scanner is None:
            raise NotFoundError("Scanner device not found", details={"scanner_id": str(scanner_id)})

        if payload.name is not None:
            scanner.name = normalize_scanner_device_key(payload.name)
        if payload.enabled is not None:
            scanner.enabled = bool(payload.enabled)
        if payload.live_page_mode is not None:
            scanner.live_page_mode = bool(payload.live_page_mode)
        scanner.updated_at = datetime.now(timezone.utc)
        if payload.recipient_user_ids is not None:
            self._set_recipients(scanner.id, payload.recipient_user_ids)

        self.db.commit()
        self.db.refresh(scanner)
        recipients = self._recipients_for([scanner.id]).get(scanner.id, [])
        return self._read(scanner, recipients)
