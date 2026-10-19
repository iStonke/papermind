#!/usr/bin/env python3
"""One fixed import release, invoked only by the local allow-listed Pi bridge."""
from __future__ import annotations

import base64
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

import pi_rollout as helpers

ROOT = Path('/home/jan/papermind')
CONTROL = ROOT / '.runtime/import-release-20261019'
SOURCE = CONTROL / 'source'
STATE = CONTROL / 'state.json'
OLD = CONTROL / 'previous-compose.json'
NEW = CONTROL / 'candidate-compose.json'
BASE = '575d9b375f9ebde219f72df8bb7f5a86df72e529'
TARGET = '8d87348e079477d304a61523e5a7187155187f2b'
ARCHIVE_SHA256 = '93ae3ca356f66b9c7beb11396160ac511b15a1be37bb0a7ca2bc5c74d9108f7c'
SCHEMA = '114_import_receipts'
SERVICES = ('backend', 'worker', 'frontend')
ALL_SERVICES = ('db', 'ai', 'backend', 'frontend', 'caddy', 'worker')
GUARD_NAME = 'papermind-import-release-20261019-guard'
GUARD = helpers.GUARD.replace('rollout-guard', 'import-release-20261019-guard')
READY = helpers.READY.replace('rollout-guard', 'import-release-20261019-guard')
RELEASE = helpers.RELEASE.replace('rollout-guard', 'import-release-20261019-guard')

IDLE = '''from app.db.session import SessionLocal
from app.services.maintenance import is_maintenance_active
from app.services.scanners import is_scanning_active
from app.models.scanner import ScannerDevice
from sqlalchemy import text,select
assert not is_maintenance_active(), 'Another maintenance operation is active'
with SessionLocal() as db:
 db.execute(text('SET TRANSACTION READ ONLY'))
 assert db.scalar(text("SELECT version_num FROM alembic_version")) == '113_drop_note_favorite'
 assert db.scalar(text("SELECT count(*) FROM jobs WHERE status IN ('queued','running')")) == 0, 'Jobs are active'
 assert db.scalar(text("SELECT count(*) FROM backup_runs WHERE status='running'")) == 0, 'Backup is active'
 assert db.scalar(text("SELECT count(*) FROM scanner_scan_jobs WHERE state IN ('queued','scanning','processing')")) == 0, 'Scanner jobs are active'
 assert not any(is_scanning_active(scanner) for scanner in db.scalars(select(ScannerDevice))), 'Scanner is active'
print('idle schema-113 production confirmed')
'''

BACKUP = '''from app.db.session import SessionLocal
from app.services.backup import BackupService
from app.services.backup_crypto import backup_encryption_key,manifest_hmac,sha256_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hmac,json
directory=Path('/data/storage/.papermind-system/import-release-20261019-backup')
assert not directory.is_symlink()
with SessionLocal() as db:
 r=BackupService(db).run_backup(kind='manual',apply_retention=False,preserve_to=directory)
 assert r.status=='success','Fresh backup failed'
 manifest_path=directory/'manifest.json'
 assert not manifest_path.is_symlink()
 manifest=json.loads(manifest_path.read_text())
 unsigned=dict(manifest);signature=unsigned.pop('hmac_sha256')
 key=backup_encryption_key();assert key is not None and manifest['encrypted'] is True
 assert hmac.compare_digest(signature,manifest_hmac(unsigned,key))
 assert manifest['database']['alembic_revision']=='113_drop_note_favorite'
 assert timedelta(0)<=datetime.now(timezone.utc)-r.started_at<=timedelta(minutes=60)
 artifacts=manifest['artifacts']
 assert len(artifacts)==2 and {a['filename'] for a in artifacts}=={'database.dump.enc','storage.tar.gz.enc'}
 size=manifest_path.stat().st_size
 for artifact in artifacts:
  path=directory/artifact['filename']
  assert not path.is_symlink() and path.stat().st_size==artifact['size_bytes'] and sha256_file(path)==artifact['sha256']
  size+=path.stat().st_size
 assert size==r.size_bytes
 print(json.dumps({'backup_id':str(r.id),'bytes':r.size_bytes,'verified_encrypted':True}))
'''

VERIFY = helpers.VERIFY.replace('113_drop_note_favorite', SCHEMA) + '''
import os,urllib.error
assert os.environ.get('APP_REVISION') == '8d87348e079477d304a61523e5a7187155187f2b'
with SessionLocal() as db:
 assert db.scalar(text("SELECT count(*) FROM pg_indexes WHERE indexname='uq_documents_import_receipt'")) == 1
try:
 urllib.request.urlopen('http://127.0.0.1:8040/api/documents',timeout=10)
except urllib.error.HTTPError as exc:
 assert exc.code==401
else: raise RuntimeError('Anonymous document access was accepted')
assert urllib.request.urlopen('http://frontend/healthz',timeout=10).status==200
print('import receipt index, application revision, anonymous denial and frontend checked')
'''


def update(phase, **fields):
    value = json.loads(STATE.read_text()) if STATE.exists() else {}
    value.update(phase=phase, **fields)
    helpers.atomic_json(STATE, value)
    print(phase, flush=True)


def preflight(expected=BASE):
    assert helpers.command(['git', 'rev-parse', 'HEAD'], log=False).strip() == expected, 'Pi source revision changed'
    assert not helpers.command(['git', 'status', '--porcelain', '--untracked-files=no'], log=False).strip(), 'Tracked source changed'
    assert os.getuid() == 1000 and os.getgid() == 1000, 'Production identity changed'
    result = {}
    for name in ALL_SERVICES:
        identifier = helpers.command(['docker', 'compose', '--env-file', '.env.prod', '-f', 'docker-compose.prod.yml', 'ps', '-q', name], log=False).strip()
        assert identifier, 'Missing service: ' + name
        state = json.loads(helpers.command(['docker', 'inspect', '--format', '{{json .State}}', identifier], log=False))
        assert state['Running'] and state.get('Health', {}).get('Status', 'healthy') == 'healthy', 'Unhealthy service: ' + name
        result[name] = {'container': identifier, 'image': helpers.command(['docker', 'inspect', '--format', '{{.Image}}', identifier], log=False).strip()}
    return result


def validate_payload(raw):
    assert len(raw) <= 12 * 1024 * 1024, 'Release request too large'
    payload = json.loads(raw)
    assert set(payload) == {'archive_base64', 'archive_sha256'} and payload['archive_sha256'] == ARCHIVE_SHA256, 'Only the fixed release is accepted'
    archive = base64.b64decode(payload['archive_base64'], validate=True)
    assert len(archive) <= helpers.MAX_ARCHIVE_BYTES and hashlib.sha256(archive).hexdigest() == ARCHIVE_SHA256, 'Release checksum mismatch'
    return archive


def validate_source():
    archive = (CONTROL / 'release.tar.gz').read_bytes()
    assert hashlib.sha256(archive).hexdigest() == ARCHIVE_SHA256, 'Release archive changed'
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            path = SOURCE / member.name
            assert path.is_file() and not path.is_symlink(), 'Staged source missing'
            assert path.read_bytes() == tar.extractfile(member).read(), 'Staged source changed'


def prepare():
    validate_source()
    before = preflight()
    assert helpers.shutil.disk_usage(ROOT).free >= 8 * 1024**3, 'Insufficient build and recovery space'
    old, new = helpers.read_config(ROOT), helpers.read_config(SOURCE)
    for name in ALL_SERVICES:
        old['services'][name].pop('build', None)
        old['services'][name]['image'] = before[name]['image']
    for name in SERVICES:
        new['services'][name]['build']['context'] = str(SOURCE if name == 'worker' else SOURCE / name)
        new['services'][name]['image'] = f'papermind-import-{name}:{TARGET[:12]}'
        if name in ('backend', 'worker'): new['services'][name]['environment']['APP_REVISION'] = TARGET
    helpers.atomic_json(OLD, old)
    helpers.atomic_json(NEW, new)
    helpers.compose(OLD, 'exec', '-T', 'backend', 'python', '-c', IDLE, log=False, timeout=30)
    helpers.command(['git', 'fetch', '--no-tags', 'origin', 'feat/ki-chat-integration'], log=False)
    assert helpers.command(['git', 'rev-parse', TARGET], log=False).strip() == TARGET
    helpers.command(['git', 'merge-base', '--is-ancestor', BASE, TARGET], log=False)
    update('building', status='running', before=before)
    images = {}
    for name in SERVICES:
        update('building_' + name)
        helpers.compose(NEW, 'build', name, timeout=3600)
        images[name] = helpers.command(['docker', 'image', 'inspect', '--format', '{{.Id}}', new['services'][name]['image']], log=False).strip()
    helpers.compose(NEW, 'run', '--rm', '--no-deps', 'backend', 'python', '-c', helpers.PREFLIGHT, timeout=180)
    assert preflight() == before, 'Production changed during build'
    update('prepared', status='prepared', images=images)


def apply():
    state = json.loads(STATE.read_text())
    validate_source()
    assert preflight() == state['before'], 'Production changed since preparation'
    old, new = json.loads(OLD.read_text()), json.loads(NEW.read_text())
    for name in SERVICES:
        image = helpers.command(['docker', 'image', 'inspect', '--format', '{{.Id}}', new['services'][name]['image']], log=False).strip()
        assert image == state['images'][name], 'Candidate image changed'
    switched = git_changed = guard_started = False
    try:
        helpers.compose(OLD, 'exec', '-T', 'backend', 'python', '-c', IDLE, log=False, timeout=30)
        update('backup', status='running')
        backup = helpers.compose(OLD, 'run', '--rm', '--no-deps', '--name', 'papermind-import-release-20261019-backup', 'backend', 'python', '-c', BACKUP, log=False, timeout=3600)
        backup = json.loads(backup.strip().splitlines()[-1])
        assert backup['verified_encrypted'] is True
        update('draining_writes', backup=backup)
        helpers.compose(OLD, 'run', '-d', '--no-deps', '--name', GUARD_NAME, 'backend', 'python', '-c', GUARD, log=False)
        guard_started = True
        deadline = time.monotonic() + 960
        while True:
            try:
                helpers.command(['docker', 'exec', GUARD_NAME, 'python', '-c', READY], log=False, timeout=10)
                break
            except RuntimeError:
                assert time.monotonic() < deadline, 'Writes did not drain'
                time.sleep(2)
        assert preflight() == state['before'], 'Production changed before switching'
        update('stopping_services')
        switched = True
        helpers.compose(OLD, 'stop', 'worker', 'backend', 'frontend', timeout=180)
        helpers.command(['git', 'merge', '--ff-only', TARGET], log=False)
        git_changed = True
        update('migrating')
        helpers.compose(NEW, 'run', '--rm', '--no-deps', 'backend', 'alembic', 'upgrade', SCHEMA, timeout=900)
        update('starting_services')
        helpers.compose(NEW, 'up', '-d', '--no-build', '--no-deps', '--wait', '--wait-timeout', '180', 'backend', 'frontend', timeout=240)
        helpers.compose(NEW, 'exec', '-T', 'backend', 'python', '-c', VERIFY, timeout=60)
        helpers.compose(NEW, 'up', '-d', '--no-build', '--no-deps', '--wait', '--wait-timeout', '180', 'worker', timeout=240)
        after = preflight(TARGET)
        assert all(after[name] == state['before'][name] for name in ('db', 'ai', 'caddy')), 'Unrelated services changed'
        for name in SERVICES: helpers.command(['docker', 'tag', state['images'][name], f'papermind-{name}:latest'], log=False)
        helpers.atomic_json(CONTROL / 'installed.json', {'head': TARGET, 'schema': SCHEMA, 'archive_sha256': ARCHIVE_SHA256})
        update('complete', status='success', head=TARGET, schema=SCHEMA)
    except Exception as exc:
        rollback_ok = not switched
        if switched:
            update('rolling_back', error_type=type(exc).__name__)
            try:
                helpers.compose(NEW, 'stop', 'worker', 'backend', 'frontend', timeout=180)
                helpers.compose(NEW, 'run', '--rm', '--no-deps', 'backend', 'alembic', 'downgrade', '113_drop_note_favorite', timeout=900)
                if git_changed:
                    assert helpers.command(['git', 'rev-parse', 'HEAD'], log=False).strip() == TARGET
                    assert not helpers.command(['git', 'status', '--porcelain', '--untracked-files=no'], log=False).strip()
                    helpers.command(['git', 'reset', '--hard', BASE], log=False)
                for name in SERVICES: helpers.command(['docker', 'tag', old['services'][name]['image'], f'papermind-{name}:latest'], log=False)
                helpers.compose(OLD, 'up', '-d', '--no-build', '--no-deps', '--wait', '--wait-timeout', '180', 'backend', 'frontend', 'worker', timeout=300)
                preflight()
                rollback_ok = True
            except Exception as rollback:
                print('Rollback failed: ' + type(rollback).__name__, flush=True)
        update('failed', status='failed', error_type=type(exc).__name__, rollback_ok=rollback_ok)
        raise
    finally:
        if guard_started:
            helpers.command(['docker', 'exec', GUARD_NAME, 'python', '-c', RELEASE], log=False, check=False, timeout=10)
            time.sleep(2)
            helpers.command(['docker', 'rm', '-f', GUARD_NAME], log=False, check=False, timeout=30)


def start(mode):
    CONTROL.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (CONTROL / 'admission.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        assert state.get('status') not in {'running', 'success'}, 'Release active or complete'
        if mode == 'prepare':
            archive = validate_payload(sys.stdin.read(12 * 1024 * 1024 + 1))
            preflight()
            if SOURCE.exists(): validate_source()
            else:
                SOURCE.mkdir(mode=0o700)
                names = helpers.unpack(archive, SOURCE)
                assert f'backend/alembic/versions/{SCHEMA}.py' in names, 'Import receipt migration missing'
                (CONTROL / 'release.tar.gz').write_bytes(archive)
                (CONTROL / 'release.tar.gz').chmod(0o600)
        else: assert mode == 'apply' and state.get('status') == 'prepared', 'Release not prepared'
        update('starting_' + mode, status='running')
        with (CONTROL / 'release.log').open('w') as log:
            os.chmod(log.name, 0o600)
            process = subprocess.Popen([sys.executable, __file__, '--run-' + mode], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        print(json.dumps({'status': 'started', 'mode': mode, 'pid': process.pid}))


def status():
    print(STATE.read_text() if STATE.exists() else '{"status":"not_started"}')
    log = CONTROL / 'release.log'
    if log.exists(): print(log.read_text(errors='replace')[-8000:])


def main():
    args = sys.argv[1:]
    if args == ['--prepare']: start('prepare')
    elif args == ['--apply']: start('apply')
    elif args in (['--run-prepare'], ['--run-apply']):
        try:
            if args == ['--run-prepare']: prepare()
            else: apply()
        except Exception as exc:
            state = json.loads(STATE.read_text())
            if state.get('status') != 'failed': update('failed', status='failed', error_type=type(exc).__name__, rollback_ok=True)
            raise
    elif args == ['--status']: status()
    elif args == ['--inspect']:
        before = preflight()
        helpers.read_config(ROOT)
        helpers.command(['docker', 'exec', before['backend']['container'], 'python', '-c', IDLE], log=False, timeout=30)
        print(json.dumps({'head': BASE, 'services_healthy': list(before), 'free_bytes': helpers.shutil.disk_usage(ROOT).free, 'idle': True}))
    elif args == ['--verify']:
        preflight(TARGET)
        helpers.read_config(ROOT)
        helpers.compose(NEW, 'exec', '-T', 'backend', 'python', '-c', VERIFY, timeout=60)
    else: raise ValueError('Unsupported fixed import release operation')


if __name__ == '__main__': main()
