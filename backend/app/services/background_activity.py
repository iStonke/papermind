"""Shared, owner-scoped controls for cooperative background work.

Native operations finish their current step; cancellation is observed at the next
checkpoint. A restart is queued only after the previous execution has unwound.
"""
import fcntl
import json
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from app.core.config import get_settings

_context = threading.local()


class ActivityCancelled(BaseException):
    pass


def _root():
    root = Path(get_settings().storage_path) / '.background-activity'
    root.mkdir(parents=True, exist_ok=True)
    return root


@contextmanager
def _lock():
    with (_root() / '.lock').open('a+b') as file:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def _read(job_id):
    path = _root() / f'{uuid.UUID(str(job_id))}.json'
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _write(item):
    item['updated_at'] = datetime.now(timezone.utc).isoformat()
    path = _root() / f"{item['id']}.json"
    temp = path.with_suffix(f'.{uuid.uuid4().hex}.tmp')
    temp.write_text(json.dumps(item, default=str))
    os.replace(temp, path)


def activity(owner_id, *, admin=False):
    items = []
    with _lock():
        for path in _root().glob('*.json'):
            item = _read(path.stem)
            if item and (item['owner_id'] == str(owner_id) or (admin and item['kind'] == 'backup')) and item['status'] != 'done':
                items.append({key: value for key, value in item.items() if key not in {'args', 'kwargs', 'owner_id'}})
    return items


def control(job_id, action, owner_id, *, admin=False):
    from app.core.errors import ConflictError, NotFoundError
    with _lock():
        item = _read(job_id)
        if not item or not (item['owner_id'] == str(owner_id) or (admin and item['kind'] == 'backup')):
            raise NotFoundError('Vorgang nicht gefunden')
        if item['status'] == 'running':
            item['cancel_requested'] = True
            item['restart_requested'] = action == 'restart'
            item['phase'] = 'Wird neu gestartet' if action == 'restart' else 'Wird beendet'
        elif action == 'restart':
            item.update(status='queued', cancel_requested=False, restart_requested=False, error_message=None)
        elif item['status'] == 'queued':
            item.update(status='cancelled', cancel_requested=False)
        else:
            raise ConflictError('Der Vorgang ist bereits beendet')
        _write(item)


def checkpoint():
    job_id = getattr(_context, 'job_id', None)
    if job_id:
        with _lock():
            item = _read(job_id)
            if not item or item.get('cancel_requested'):
                raise ActivityCancelled()


def tracked(kind, title):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            owner = kwargs.get('owner_id') or (args[1] if len(args) > 1 else None)
            item = dict(id=str(uuid.uuid4()), kind=kind, title=title, owner_id=str(owner),
                        status='running', cancel_requested=False, restart_requested=False,
                        args=[str(v) if isinstance(v, uuid.UUID) else v for v in args], kwargs=kwargs)
            with _lock():
                _write(item)
            return execute(item, function)
        wrapped.activity_function = function
        return wrapped
    return decorate


def execute(item, function):
    previous = getattr(_context, 'job_id', None)
    _context.job_id = item['id']
    status, error = 'done', None
    try:
        checkpoint()
        result = function(*item.get('args', []), **item.get('kwargs', {}))
        checkpoint()
        if getattr(result, "status", None) == "failed":
            status, error = "failed", getattr(result, "error", None)
        return result
    except ActivityCancelled:
        status = 'cancelled'
    except Exception as exc:
        status, error = 'failed', str(exc)[:500]
        raise
    finally:
        _context.job_id = previous
        with _lock():
            current = _read(item['id'])
            restart = current.get('restart_requested', False)
            current.update(status='queued' if restart else status, cancel_requested=False,
                           restart_requested=False, error_message=error, phase=None)
            _write(current)


def claim_queued(kinds):
    with _lock():
        for path in _root().glob('*.json'):
            item = _read(path.stem)
            if item and item['kind'] in kinds and item['status'] == 'queued':
                item['status'] = 'running'
                _write(item)
                return item
    return None


def dismiss(job_id, owner_id, *, admin=False):
    from app.core.errors import ConflictError, NotFoundError
    with _lock():
        item = _read(job_id)
        if not item or not (item['owner_id'] == str(owner_id) or (admin and item['kind'] == 'backup')):
            raise NotFoundError('Vorgang nicht gefunden')
        if item['status'] in {'queued', 'running'}:
            raise ConflictError('Ein laufender Vorgang kann nicht entfernt werden')
        (_root() / f'{uuid.UUID(str(job_id))}.json').unlink()


def recover_interrupted(kinds):
    with _lock():
        for path in _root().glob('*.json'):
            item = _read(path.stem)
            if item and item['kind'] in kinds and item['status'] == 'running':
                item.update(status='failed', phase=None, cancel_requested=False,
                            error_message='Verarbeitung durch Worker-Neustart unterbrochen')
                _write(item)
