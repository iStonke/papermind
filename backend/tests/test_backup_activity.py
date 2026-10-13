import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models.backup_run import BackupRun
from app.services import background_activity
from app.services.backup import BackupService, run_backup_in_background


@pytest.mark.parametrize("kind", ["manual", "scheduled"])
@pytest.mark.parametrize("queued", [False, True])
@pytest.mark.parametrize(
    ("status", "error", "activity_status"),
    [
        ("success", None, "done"),
        ("skipped", None, "done"),
        ("failed", "NAS nicht erreichbar", "failed"),
    ],
)
def test_backup_activity_keeps_result_after_session_closes(tmp_path, kind, queued, status, error, activity_status):
    engine = create_engine("sqlite://")
    BackupRun.__table__.create(engine)
    db = Session(engine)
    run = BackupRun(
        id=uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        status=status,
        kind=kind,
        error=error,
    )

    def finish_backup(service, *, kind):
        assert service.db is db
        assert kind == run.kind
        db.add(run)
        db.commit()
        db.refresh(run)
        # Releasing the backup operation lock commits once more, expiring the
        # result even though run_backup refreshed it before returning.
        db.commit()
        assert inspect(run).expired
        return run

    try:
        with (
            patch("app.db.session.SessionLocal", return_value=db),
            patch.object(BackupService, "run_backup", autospec=True, side_effect=finish_backup),
            patch.object(background_activity, "_root", return_value=tmp_path),
        ):
            if queued:
                # Restarts call activity_function directly through execute.
                item = {
                    "id": str(uuid.uuid4()), "kind": "backup", "title": "NAS-Backup",
                    "owner_id": "None", "status": "running", "args": [], "kwargs": {"kind": kind},
                }
                background_activity._write(item)
                result = background_activity.execute(item, run_backup_in_background.activity_function)
            else:
                result = run_backup_in_background(kind=kind)

            assert inspect(run).detached
            assert result.status == status
            assert result.error == error
            activity = json.loads(next(tmp_path.glob("*.json")).read_text())
            assert activity["status"] == activity_status
            assert activity["error_message"] == error
    finally:
        db.close()
        engine.dispose()
