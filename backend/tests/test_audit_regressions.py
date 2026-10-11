import asyncio
import hashlib
import json
import subprocess
import uuid
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from sqlalchemy import inspect, select, text
from starlette.requests import Request

from app.core.config import get_settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError, StorageError, install_exception_handlers
from app.core.security import client_ip
from app.core.upload_guard import UploadAuthMiddleware
from app.db.session import SessionLocal
from app.models.annotation import Annotation
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.user import User
from app.schemas.documents import PageReorderRequest
from app.schemas.notes import NoteCreateRequest
from app.services.document_storage import DocumentStorageService
from app.services.documents import DocumentService
from app.services.import_staging import ImportStagingService
from app.services.note_audio_jobs import NoteAudioJobStore
from app.services.note_service import NoteService
from app.services.storage_cleanup import retry_user_cleanups, run_user_cleanup, schedule_user_cleanup
from app.services.users import UserService


def request(*, forwarded='', peer='192.0.2.10'):
    return Request({'type': 'http', 'method': 'POST', 'path': '/api/auth/login',
        'headers': [(b'x-forwarded-for', forwarded.encode())], 'client': (peer, 1234)})


def test_validation_errors_are_422_and_do_not_echo_secrets():
    app = FastAPI()
    install_exception_handlers(app)
    @app.post('/test')
    def endpoint(payload: PageReorderRequest): return {'ok': True}
    response = TestClient(app, raise_server_exceptions=False).post('/test', json={'order': [1, 1]})
    assert response.status_code == 422
    assert response.json()['error']['details'][0]['loc'] == ['body', 'order']
    assert 'input' not in response.json()['error']['details'][0]
    assert 'ctx' not in response.json()['error']['details'][0]


def test_http_error_headers_survive_custom_handler():
    app = FastAPI()
    install_exception_handlers(app)
    @app.get('/test')
    def endpoint(): raise HTTPException(429, 'limited', headers={'Retry-After': '60'})
    assert TestClient(app).get('/test').headers['retry-after'] == '60'


def test_anonymous_upload_is_rejected_before_multipart_parsing():
    app = FastAPI()
    app.add_middleware(UploadAuthMiddleware)
    @app.post('/api/upload')
    def endpoint(file: UploadFile = File(...)): return {'ok': True}
    with patch('app.core.upload_guard._authorized', return_value=False), patch('python_multipart.MultipartParser.write') as parse:
        response = TestClient(app).post('/api/upload', files={'file': ('scan.pdf', b'%PDF-test', 'application/pdf')})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'
    parse.assert_not_called()


@pytest.mark.parametrize('declared', [True, False])
def test_upload_size_is_bounded_before_or_during_body_parsing(monkeypatch, declared):
    monkeypatch.setattr(get_settings(), 'upload_max_bytes', 10)
    monkeypatch.setattr(get_settings(), 'upload_request_max_bytes', 10)
    app = FastAPI()
    install_exception_handlers(app)
    app.add_middleware(UploadAuthMiddleware)
    @app.post('/api/upload')
    def endpoint(file: UploadFile = File(...)): return {'ok': True}
    content = (b'--test\r\nContent-Disposition: form-data; name="file"; filename="test.pdf"\r\n'
        b'Content-Type: application/pdf\r\n\r\n' + b'x' * (1024 * 1024 + 100) + b'\r\n--test--\r\n')
    with patch('app.core.upload_guard._authorized', return_value=True):
        response = TestClient(app).post('/api/upload',
            content=content if declared else iter([content[:200], content[200:]]),
            headers={'Content-Type': 'multipart/form-data; boundary=test'})
    assert response.status_code == 413


def test_untrusted_forwarded_header_cannot_change_client_identity(monkeypatch):
    monkeypatch.setattr(get_settings(), 'auth_trusted_proxy_cidrs', '')
    assert client_ip(request(forwarded='203.0.113.1')) == '192.0.2.10'
    assert client_ip(request(forwarded='203.0.113.2')) == '192.0.2.10'


def test_trusted_proxy_chain_stops_at_first_untrusted_address(monkeypatch):
    monkeypatch.setattr(get_settings(), 'auth_trusted_proxy_cidrs', '172.20.0.0/16')
    assert client_ip(request(peer='172.20.0.5', forwarded='198.51.100.99, 203.0.113.10, 172.20.0.3')) == '203.0.113.10'


def test_production_requires_a_nonprivileged_web_role(monkeypatch):
    from app.core.production import validate_production_security
    from app.db.session import AppSessionLocal
    settings = get_settings()
    monkeypatch.setattr(settings, 'production_mode', True)
    monkeypatch.setattr(settings, 'auth_secret_key', 'x' * 64)
    monkeypatch.setattr(settings, 'auth_enabled', True)
    monkeypatch.setattr(settings, 'auth_cookie_secure', True)
    validate_production_security(settings, AppSessionLocal)
    with pytest.raises(RuntimeError, match='must not bypass'):
        validate_production_security(settings, SessionLocal)
    monkeypatch.setattr(settings, 'app_database_url', '')
    with pytest.raises(RuntimeError, match='separate APP_DATABASE_URL'):
        validate_production_security(settings, AppSessionLocal)


def test_unknown_account_still_performs_scrypt():
    import app.core.auth as auth
    service = UserService(MagicMock())
    service.get_by_username = lambda _: None
    service.get_by_email_login = lambda _: None
    with patch.object(auth.hashlib, 'scrypt', wraps=auth.hashlib.scrypt) as derive:
        assert service.authenticate('unknown', 'test-password') is None
    derive.assert_called_once()


def test_case_and_whitespace_variants_share_the_same_login_limit(owner, monkeypatch):
    from app.routers.auth import login
    from app.schemas.auth import LoginRequest
    from fastapi import Response
    monkeypatch.setattr(get_settings(), 'auth_login_rate_limit', 2)
    with SessionLocal() as db:
        username = db.get(User, owner).username
        for variant, expected in [(username, 401), (username.upper(), 401), (f'  {username}  ', 429)]:
            with pytest.raises(Exception) as raised:
                login(LoginRequest(username=variant, password='incorrect'), request(), Response(), db)
            assert raised.value.status_code == expected


@pytest.fixture
def owner(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), 'storage_path', str(tmp_path))
    with SessionLocal() as db:
        user = User(username=f'audit-{uuid.uuid4().hex}', password_hash='x', is_active=True)
        db.add(user); db.commit()
        user_id = user.id
    yield user_id
    with SessionLocal() as db:
        db.execute(text('DELETE FROM users WHERE id=:id'), {'id': user_id}); db.commit()


def write_pdf(path, widths):
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for width in widths: writer.add_blank_page(width=width, height=200)
    writer.write(str(path))


def widths(path):
    return [float(page.mediabox.width) for page in PdfReader(str(path)).pages]


def create_document(owner_id, root, *, ocr_widths=(100, 200)):
    with SessionLocal() as db:
        doc = Document(owner_id=owner_id, original_filename='test.pdf', page_count=2)
        db.add(doc); db.flush()
        directory = root / str(doc.id)
        for role, pages in [('original', [100, 200]), ('ocr', ocr_widths)]:
            path = directory / f'{role}.pdf'; write_pdf(path, pages)
            key = str(path.relative_to(root))
            db.add(DocumentFile(document_id=doc.id, role=role, file_key=key, mime_type='application/pdf', bytes=path.stat().st_size))
            if role == 'original':
                doc.storage_key = key
                doc.file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        db.add(Annotation(document_id=doc.id, page=1, rects=[]))
        db.commit()
        return doc.id, directory


def test_later_pdf_failure_keeps_all_published_files_and_annotations(owner, tmp_path):
    doc_id, directory = create_document(owner, tmp_path, ocr_widths=[100, 200, 300])
    with SessionLocal() as db:
        with pytest.raises(BadRequestError): DocumentService(db, owner).reorder_pages(doc_id, [2, 1])
    assert widths(directory / 'original.pdf') == [100, 200]
    assert widths(directory / 'ocr.pdf') == [100, 200, 300]
    assert sorted(path.name for path in directory.glob('*.pdf')) == ['ocr.pdf', 'original.pdf']
    with SessionLocal() as db:
        assert db.scalar(select(Annotation.page).where(Annotation.document_id == doc_id)) == 1


def test_commit_failure_keeps_previous_pdf_references(owner, tmp_path):
    doc_id, directory = create_document(owner, tmp_path)
    with SessionLocal() as db, patch.object(db, 'commit', side_effect=RuntimeError('commit failed')):
        with pytest.raises(RuntimeError): DocumentService(db, owner).reorder_pages(doc_id, [2, 1])
    assert widths(directory / 'original.pdf') == [100, 200]
    with SessionLocal() as db:
        assert db.get(Document, doc_id).storage_key.endswith('/original.pdf')
        assert db.scalar(select(Annotation.page).where(Annotation.document_id == doc_id)) == 1


def test_reordered_files_hash_annotations_and_job_are_published_together(owner, tmp_path):
    doc_id, directory = create_document(owner, tmp_path)
    with SessionLocal() as db:
        updated = DocumentService(db, owner).reorder_pages(doc_id, [2, 1])
        new_path = tmp_path / updated.storage_key
        assert widths(new_path) == [200, 100]
        assert updated.file_sha256 == hashlib.sha256(new_path.read_bytes()).hexdigest()
        assert db.scalar(select(Annotation.page).where(Annotation.document_id == doc_id)) == 2
        assert db.scalar(text("SELECT count(*) FROM jobs WHERE document_id=:id AND type='INDEX' AND status='queued'"), {'id': doc_id}) == 1
        assert widths(directory / 'original.pdf') == [100, 200]
        with pytest.raises(ConflictError): DocumentService(db, owner).reorder_pages(doc_id, [2, 1])


def test_giant_pdf_page_renders_directly_to_small_thumbnail(tmp_path):
    source = tmp_path / 'giant.pdf'; write_pdf(source, [20000])
    storage = DocumentStorageService(storage_path=str(tmp_path), upload_max_bytes=10000, text_check_pages=2)
    result = storage.create_thumbnail(uuid.uuid4(), source)
    assert result is not None
    from PIL import Image
    with Image.open(tmp_path / result[0]) as image:
        assert max(image.size) <= 320


def test_pdf_processing_timeout_releases_the_processing_slot(tmp_path):
    from app.services.pdf_tasks import run_pdf_task
    with patch('app.services.pdf_tasks.subprocess.run', side_effect=subprocess.TimeoutExpired('pdf', 30)):
        with pytest.raises(StorageError): run_pdf_task('quick_text', storage_path=str(tmp_path), path='unused')
    source = tmp_path / 'normal.pdf'; write_pdf(source, [100])
    assert run_pdf_task('quick_text', storage_path=str(tmp_path), path=str(source))[3] == 1


def test_import_preview_ocr_caps_giant_pages_before_rendering(tmp_path):
    from app.services.ocr_pipeline import _run_ocr_lite
    from PIL import Image
    source=tmp_path/'giant-ocr.pdf';write_pdf(source,[20000])
    def recognize(command,**kwargs):
        with Image.open(command[1]) as image:
            assert max(image.size)<=600
        assert kwargs['timeout']==3
        return subprocess.CompletedProcess(command,0,'Synthetic OCR text','')
    with patch('app.services.ocr_pipeline.subprocess.run',side_effect=recognize):
        assert _run_ocr_lite(source,max_long_side_px=600,timeout_seconds=3)=='Synthetic OCR text'


def test_import_preview_ocr_uses_bounded_pdf_subprocess(tmp_path):
    from app.services.ocr_pipeline import run_ocr_lite
    with patch('app.services.pdf_tasks.run_pdf_task',return_value='Preview') as task:
        assert run_ocr_lite(tmp_path/'input.pdf',max_long_side_px=2400)=='Preview'
    assert task.call_args.args==('ocr_lite',)
    assert task.call_args.kwargs['max_long_side_px']==2400


def test_deleted_account_media_and_running_audio_cannot_be_republished(owner, tmp_path):
    audio = NoteAudioJobStore(tmp_path)
    job = audio.create(owner_id=owner, note_id=uuid.uuid4(), note_title='Private', text='Private text', voice='standard')
    audio.claim_next('test-worker')
    other_owner = uuid.uuid4()
    artifacts = [f'avatars/{owner}.webp', f'note-images/{owner}/note/image.png', f'dossier-images/{owner}/image.png']
    for key in artifacts + [f'note-images/{other_owner}/safe.png']:
        path = tmp_path / key; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'test')
    source_id = uuid.uuid4(); staging = tmp_path / 'import_staging'; staging.mkdir()
    (staging / f'{source_id}.pdf').write_bytes(b'test')
    (staging / f'{source_id}.owner.json').write_text(json.dumps({'owner_id': str(owner)}))
    with SessionLocal() as db: UserService(db)._purge_user(db.get(User, owner))
    assert all(not (tmp_path / key).exists() for key in artifacts)
    assert (tmp_path / f'note-images/{other_owner}/safe.png').exists()
    assert not (staging / f'{source_id}.pdf').exists()
    assert audio.get(job['id']) is None
    incoming = tmp_path / 'incoming.wav'; incoming.write_bytes(b'new audio')
    assert not audio.complete(job['id'], incoming)
    assert not incoming.exists()


def test_avatar_request_authenticated_before_account_deletion_cannot_publish_afterwards(owner, tmp_path):
    from app.core.errors import UnauthorizedError
    with SessionLocal() as db:
        stale_user = db.get(User, owner)
        UserService(db)._purge_user(stale_user)
        with patch('app.services.users.process_avatar_image') as process:
            with pytest.raises(UnauthorizedError):
                UserService(db).set_avatar(stale_user, b'old request', 'image/png')
        process.assert_not_called()
    assert not (tmp_path / f'avatars/{owner}.webp').exists()


def test_cleanup_task_never_deletes_a_live_account_and_retries_after_io_failure(owner, tmp_path):
    image = tmp_path / f'note-images/{owner}/image.png'; image.parent.mkdir(parents=True); image.write_bytes(b'private')
    task = schedule_user_cleanup(owner, document_ids=[], file_keys=[], source_ids=[])
    with SessionLocal() as db:
        assert not run_user_cleanup(db, task)
        assert image.exists()
        db.execute(text('DELETE FROM users WHERE id=:id'), {'id': owner}); db.commit()
        with patch('app.services.storage_cleanup.shutil.rmtree', side_effect=OSError('busy')):
            with pytest.raises(OSError): run_user_cleanup(db, task)
        assert task.exists()
        assert retry_user_cleanups(db) == 1
    assert not image.exists() and not task.exists()


def test_staging_source_uuid_does_not_grant_access_to_another_owner(owner, tmp_path):
    source = uuid.uuid4(); staging = tmp_path / 'import_staging'; staging.mkdir()
    (staging / f'{source}.pdf').write_bytes(b'%PDF-test')
    (staging / f'{source}.owner.json').write_text(json.dumps({'owner_id': str(uuid.uuid4())}))
    with SessionLocal() as db:
        with pytest.raises(NotFoundError): ImportStagingService(db, owner).get_source_pdf_path(str(source))
    (staging / f'{source}.owner.json').write_text(json.dumps({'owner_id': str(owner)}))
    with SessionLocal() as db:
        assert ImportStagingService(db, owner).get_source_pdf_path(str(source)).exists()


def test_note_list_projects_previews_without_loading_large_bodies(owner):
    from app.models.note import Note
    body = {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Vorlauf ' * 300 + 'Fundstelle' + ' Nachlauf' * 300}]}]}
    with SessionLocal() as db:
        note = NoteService(db, owner).create_note(NoteCreateRequest(title='List', body_json=body))
        note_id = note.id
    with SessionLocal() as db:
        loaded = []
        original = db.scalars
        def capture(statement):
            rows = original(statement).all()
            loaded.extend(rows)
            return SimpleNamespace(all=lambda: rows)
        with patch.object(db, 'scalars', side_effect=capture):
            items = NoteService(db, owner).list_notes(q='Fundstelle', limit=1)
        assert len(items) == 1 and 'Fundstelle' in items[0].preview
        assert len(items[0].preview) <= 202
        assert loaded[0].id == note_id
        assert {'body_json', 'body_text', 'search_vector'} <= inspect(loaded[0]).unloaded


def test_inbox_clients_share_payload_work(monkeypatch):
    from app.routers import imports
    owner = uuid.uuid4(); calls = []
    from collections import OrderedDict
    monkeypatch.setattr(imports, '_inbox_cache', OrderedDict())
    monkeypatch.setattr(imports, '_inbox_locks', {})
    monkeypatch.setattr(imports, '_load_inbox_payload', lambda _: calls.append(1) or {'scanning': False, 'scan_jobs': []})
    async def scenario():
        results = await asyncio.gather(*(imports._cached_inbox_payload(owner) for _ in range(5)))
        assert len(calls) == 1 and all(result == results[0] for result in results)
    asyncio.run(scenario())


def test_revoked_inbox_stream_ends_without_emitting_another_payload(monkeypatch):
    from app.routers import imports
    from app.core.auth import create_access_token
    from app.core.deps import token_secret
    owner = uuid.uuid4()
    token = create_access_token(owner, token_secret(), 60)
    req = SimpleNamespace(headers={'authorization': f'Bearer {token}'}, is_disconnected=AsyncMock(return_value=False))
    monkeypatch.setattr(imports, 'SSE_SESSION_CHECK_SECONDS', 0)
    monkeypatch.setattr(imports, '_stream_session_active', lambda *_: False)
    async def scenario():
        response = await imports.stream_import_inbox_events(req, SimpleNamespace(id=owner))
        frames = [frame async for frame in response.body_iterator]
        assert frames == [': connected\n\n']
    asyncio.run(scenario())


def test_stream_guard_observes_real_session_revocation(owner):
    from app.routers.imports import _stream_session_active
    from app.core.auth import create_access_token
    from app.core.deps import token_secret
    from app.services.auth_sessions import AuthSessionService
    with SessionLocal() as db:
        user = db.get(User, owner)
        session, _ = AuthSessionService(db).create(user, request())
        token = create_access_token(owner, token_secret(), 60, session_version=user.session_version, claims={'sid': str(session.id)})
        assert _stream_session_active(token, owner)
        AuthSessionService(db).revoke_id(session.id)
        assert not _stream_session_active(token, owner)


def test_chunk_search_vector_updates_and_has_a_usable_index(owner, tmp_path):
    from app.models.document_chunk import DocumentChunk
    doc_id, _ = create_document(owner, tmp_path)
    with SessionLocal() as db:
        chunk = DocumentChunk(doc_id=doc_id, chunk_index=0, text='Rechnung', char_len=8, content_hash='a' * 64)
        db.add(chunk); db.flush()
        assert db.scalar(text("SELECT search_vector @@ plainto_tsquery('german','Rechnung') FROM doc_chunks WHERE id=:id"), {'id': chunk.id})
        chunk.text = 'Vertrag'; db.flush()
        assert not db.scalar(text("SELECT search_vector @@ plainto_tsquery('german','Rechnung') FROM doc_chunks WHERE id=:id"), {'id': chunk.id})
        db.execute(text('SET LOCAL enable_seqscan=off'))
        plan = db.scalars(text("EXPLAIN SELECT id FROM doc_chunks WHERE search_vector @@ plainto_tsquery('german','Vertrag')")).all()
        assert any('ix_doc_chunks_search_vector' in line for line in plan)


def test_system_io_does_not_block_the_api_event_loop(monkeypatch):
    from app.services import system_status
    entered, release = threading.Event(), threading.Event()
    def blocking(*_):
        entered.set(); release.wait(1); return 'snapshot'
    monkeypatch.setattr(system_status, '_collect_cpu', AsyncMock(return_value=None))
    monkeypatch.setattr(system_status, '_collect_status_sync', blocking)
    async def scenario():
        task = asyncio.create_task(system_status.collect_status(MagicMock()))
        try:
            await asyncio.wait_for(asyncio.to_thread(entered.wait), 0.5)
            assert not task.done()
        finally:
            release.set()
        assert await task == 'snapshot'
    asyncio.run(scenario())
