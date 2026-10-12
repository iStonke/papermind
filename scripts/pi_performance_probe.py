#!/usr/bin/env python3
"""Fixed read-only API probe; runs inside the production backend container."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import signal
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

SAMPLES = 20
MAX_BODY = 2 * 1024 * 1024
BASE = 'http://caddy'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def percentile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


class RateLimit:
    def __init__(self, rate):
        self.interval = 1 / rate
        self.next = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            scheduled = max(now, self.next)
            self.next = scheduled + self.interval
        time.sleep(max(0, scheduled - now))


def read_request(label, path, token, *, ranged=False):
    assert path.startswith('/api/') and not path.startswith('//')
    assert 'token=' not in path
    headers = {'Authorization': 'Bearer ' + token, 'Accept-Encoding': 'gzip'}
    if ranged:
        headers['Range'] = 'bytes=0-65535'
    start = time.perf_counter()
    result = {'label': label, 'status': 0, 'bytes': 0, 'capped': False}
    try:
        request = urllib.request.Request(BASE + path, headers=headers, method='GET')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=5) as response:
            result['ttfb_ms'] = (time.perf_counter() - start) * 1000
            encoding = response.headers.get('Content-Encoding', 'identity').lower()
            result['content_encoding'] = encoding if encoding in {'identity', 'gzip', 'br', 'zstd'} else 'other'
            data = response.read(MAX_BODY + 1)
            result.update(status=response.status, bytes=min(len(data), MAX_BODY), capped=len(data) > MAX_BODY)
    except urllib.error.HTTPError as exc:
        result['status'] = exc.code
        exc.close()
    except Exception as exc:
        result['error_type'] = type(exc).__name__
    result['elapsed_ms'] = (time.perf_counter() - start) * 1000
    return result


def plan():
    from sqlalchemy import func, select, text
    from app.core.auth import create_access_token
    from app.core.deps import token_secret
    from app.db.session import SessionLocal
    from app.models.auth_session import AuthSession
    from app.models.document import Document
    from app.models.document_file import DocumentFile
    from app.models.note import Note
    from app.models.user import User
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        assert db.scalar(text("SELECT count(*) FROM backup_runs WHERE status='running'")) == 0, 'Backup active'
        user = db.scalar(select(User).where(User.is_active.is_(True), User.is_admin.is_(True)).order_by(User.created_at).limit(1))
        assert user is not None, 'No active administrator'
        owner = user.id
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == owner,
            AuthSession.revoked_at.is_(None), AuthSession.expires_at > datetime.now(timezone.utc) + timedelta(minutes=5),
            AuthSession.session_version == user.session_version).order_by(AuthSession.created_at.desc()).limit(1))
        token = create_access_token(owner, token_secret(), 300, session_version=user.session_version,
            claims={'sid': str(session.id)} if session else None)
        dataset = {'notes': db.scalar(select(func.count()).select_from(Note).where(Note.owner_id == owner, Note.is_deleted.is_(False))),
            'documents': db.scalar(select(func.count()).select_from(Document).where(Document.owner_id == owner, Document.is_deleted.is_(False))),
            'auth': 'existing_session' if session else 'legacy_without_session_lookup'}
        cases = [('notes_list', '/api/notes?limit=500', False),
            ('documents_list', '/api/documents?limit=20&include_total=true', False),
            ('documents_search', '/api/documents?limit=20&q=Rechnung', False),
            ('notes_search', '/api/notes?limit=500&q=Test', False),
            ('import_inbox', '/api/import/inbox?limit=50', False)]
        for role, label, ranged in [('thumbnail', 'pdf_thumbnail', False), ('original', 'pdf_initial_range', True)]:
            document = db.scalar(select(Document.id).join(DocumentFile).where(Document.owner_id == owner,
                Document.is_deleted.is_(False), DocumentFile.role == role, DocumentFile.bytes <= MAX_BODY)
                .order_by(Document.created_at.desc()).limit(1))
            if document is not None:
                document = uuid.UUID(str(document))
                suffix = 'thumbnail' if role == 'thumbnail' else 'file?role=original'
                cases.append((label, f'/api/documents/{document}/{suffix}', ranged))
    return token, cases, dataset


def database_stats():
    from sqlalchemy import text
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        return dict(db.execute(text('SELECT xact_commit,xact_rollback,blks_read,blks_hit,tup_returned,tup_fetched,deadlocks '
            'FROM pg_stat_database WHERE datname=current_database()')).mappings().one())


def run(mode):
    assert mode in {'normal', 'limited_load'}
    token, cases, dataset = plan()
    concurrency, rate = (1, 2) if mode == 'normal' else (2, 4)
    limiter = RateLimit(rate)
    started = time.monotonic()
    before = database_stats()
    output = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for label, path, ranged in cases:
            expected = 206 if ranged else 200
            warmups = []
            for _ in range(2):
                limiter.wait()
                warmup = read_request(label, path, token, ranged=ranged)
                assert warmup['status'] == expected and not warmup['capped'], 'Probe warmup failed: ' + label
                warmups.append(round(warmup['elapsed_ms'], 3))
            def request(_):
                limiter.wait()
                return read_request(label, path, token, ranged=ranged)
            rows = list(pool.map(request, range(SAMPLES)))
            successful = [row for row in rows if row['status'] == expected and not row['capped']]
            times = [row['elapsed_ms'] for row in successful]
            entry = {'label': label, 'requests': len(rows), 'errors': len(rows) - len(successful),
                'content_encodings': sorted({row.get('content_encoding', 'none') for row in rows}),
                'status_counts': {str(code): sum(row['status'] == code for row in rows) for code in sorted({row['status'] for row in rows})},
                'warmup_ms': warmups, 'bytes_median': statistics.median(row['bytes'] for row in rows)}
            if times:
                entry.update(p50_ms=round(percentile(times, .5), 3), p95_ms=round(percentile(times, .95), 3),
                    max_ms=round(max(times), 3), ttfb_p50_ms=round(statistics.median(row['ttfb_ms'] for row in successful), 3))
            output.append(entry)
            if entry['errors']:
                break
            assert time.monotonic() - started < 180, 'Phase duration limit'
    after = database_stats()
    return {'mode': mode, 'concurrency': concurrency, 'max_requests_per_second': rate, 'samples_per_case': SAMPLES,
        'dataset': dataset, 'routes': output, 'elapsed_seconds': round(time.monotonic() - started, 2),
        'database_global_delta': {key: after[key] - before[key] for key in before},
        'limits': ['Pi-internal HTTP through Caddy/Nginx/backend; excludes WLAN, TLS and browser rendering',
            'Global database deltas include background traffic; 20 samples per route',
            'gzip accepted; bytes are wire bytes; successful warmed GETs; response bodies, IDs and tokens are not reported']}


if __name__ == '__main__':
    try:
        assert len(sys.argv) == 2
        signal.alarm(180)
        print(json.dumps(run(sys.argv[1])))
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}))
        sys.exit(1)
