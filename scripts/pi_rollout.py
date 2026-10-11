#!/usr/bin/env python3
"""Fixed, checksum-pinned Pi rollout. Invoked only by the local Pi bridge.

No user-provided command, host, destination, environment or image is accepted.
The release is immutable; the bridge embeds this runner before installation.
"""
from __future__ import annotations

import base64
import copy
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path('/home/jan/papermind')
CONTROL = ROOT / '.runtime/pi-rollout'
ARCHIVE_SHA256 = '8a06de418d9b7d94b9c7f775a5734e0f87bc47884e2086815c1808d19afa2dff'
BASE_COMMIT = 'fb57d08da392cd93610c9d35517c76976e488d68'
KNOWN_BASE_COMMITS = {BASE_COMMIT}
SERVICES = ('backend', 'worker', 'ai', 'frontend')
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_BYTES = 100 * 1024 * 1024
TARGET_REVISION = '113_drop_note_favorite'
STATE = CONTROL / 'state.json'
LOG = CONTROL / 'rollout.log'
_redactions = set()


def atomic_json(path, value):
    temporary = path.with_suffix('.'+str(os.getpid())+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def update(phase, **fields):
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    state.update(phase=phase, updated_at=datetime.now(timezone.utc).isoformat(), **fields)
    atomic_json(STATE, state)
    print(phase, flush=True)


def scrub(text):
    for value in sorted(_redactions, key=len, reverse=True):
        if len(value) >= 4:
            text = text.replace(value, '[redacted]')
    return re.sub(r'(https?://|postgresql(?:\+psycopg)?://)([^\s/@]+):([^\s/@]+)@', r'\1[redacted]@', text)


def command(args, *, timeout=1800, log=True, check=True):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout,
                            env={**os.environ, 'COMPOSE_PARALLEL_LIMIT': '1'})
    output = scrub(result.stdout + result.stderr)
    if log and output:
        print(output[-100000:], flush=True)
    if check and result.returncode:
        details = output[-3000:] if log else 'details suppressed'
        raise RuntimeError(f'Command {args[0]} failed with exit {result.returncode}: {details}')
    return result.stdout


def compose(path, *args, **kwargs):
    return command(['docker', 'compose', '-p', 'papermind', '-f', str(path), *args], **kwargs)


def load_release(raw):
    if len(raw) > 12 * 1024 * 1024:
        raise ValueError('Release request is too large')
    payload = json.loads(raw)
    if set(payload) != {'archive_base64', 'archive_sha256'} or payload['archive_sha256'] != ARCHIVE_SHA256:
        raise ValueError('Only the approved release is accepted')
    archive = base64.b64decode(payload['archive_base64'], validate=True)
    if len(archive) > MAX_ARCHIVE_BYTES or hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Release checksum mismatch')
    return archive


def unpack(archive, source):
    seen = set()
    total = 0
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        for member in tar:
            parts = PurePosixPath(member.name).parts
            if (not member.isfile() or not parts or member.name.startswith('/') or '..' in parts
                or any(part in {'.git', '.runtime', 'node_modules', '__pycache__', 'dist', 'test-results', 'scan-inbox', 'host-control'} for part in parts)
                or any(part.startswith('.env') and part not in {'.env.example', '.env.prod.example'} for part in parts)
                or member.name in seen):
                raise ValueError('Unsafe release member')
            total += member.size
            if total > MAX_SOURCE_BYTES or member.size < 0:
                raise ValueError('Release source is too large')
            seen.add(member.name)
            destination = source / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(tar.extractfile(member).read())
            destination.chmod(0o755 if member.mode & 0o111 else 0o644)
    required = {'docker-compose.prod.yml', 'backend/Dockerfile', 'worker/Dockerfile', 'ai/Dockerfile', 'frontend/Dockerfile.prod', f'backend/alembic/versions/{TARGET_REVISION}.py'}
    if not required <= seen:
        raise ValueError('Incomplete release')
    return seen


def read_config(source):
    output = command(['docker', 'compose', '-p', 'papermind', '--project-directory', str(ROOT),
        '--env-file', str(ROOT / '.env.prod'), '-f', str(source / 'docker-compose.prod.yml'),
        'config', '--format', 'json'], log=False)
    config = json.loads(output)
    if config.get('name') != 'papermind':
        raise ValueError('Unexpected production project')
    for service in config['services'].values():
        for key, value in service.get('environment', {}).items():
            if value and any(term in key.upper() for term in ('PASSWORD', 'SECRET', 'TOKEN', 'KEY', 'DATABASE_URL')):
                _redactions.add(str(value))
    return config


def published(name):
    parts = PurePosixPath(name).parts
    if name.endswith('Dockerfile.rollout'): return False
    return parts[0] in {'backend', 'worker', 'ai', 'frontend'} or name in {'docker-compose.prod.yml', 'deploy/Caddyfile'}


def save_and_publish(source, names, run, *, publish=False):
    backup = run / 'previous-source'
    changes = {}
    for name in sorted(names):
        if not published(name):
            continue
        destination = ROOT / name
        if destination.is_symlink() or any(parent.is_symlink() for parent in destination.parents
                                          if parent == ROOT or ROOT in parent.parents):
            raise ValueError('Symlink in production destination')
        exists = destination.exists()
        changes[name] = exists
        if not publish:
            if exists:
                previous = backup / name
                previous.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, previous)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if name == 'deploy/Caddyfile':
                # Docker's read-only single-file bind mount keeps the inode.
                # Caddy reload must see the new bytes through that same mount.
                destination.write_bytes((source / name).read_bytes())
                continue
            temporary = destination.with_name(destination.name + '.rollout-tmp')
            shutil.copy2(source / name, temporary)
            temporary.replace(destination)
    if not publish:
        atomic_json(run / 'previous-source.json', changes)


def restore_source(run):
    for name, existed in json.loads((run / 'previous-source.json').read_text()).items():
        destination = ROOT / name
        if existed:
            if name == 'deploy/Caddyfile':
                destination.write_bytes((run / 'previous-source' / name).read_bytes())
                continue
            temporary = destination.with_name(destination.name + '.rollback-tmp')
            shutil.copy2(run / 'previous-source' / name, temporary)
            temporary.replace(destination)
        else:
            destination.unlink(missing_ok=True)


PREFLIGHT = '''from app.core.config import get_settings
from app.core.production import validate_production_security
from app.db.session import AppSessionLocal
from app.services.backup_crypto import backup_encryption_key
from pathlib import Path
import importlib.metadata as metadata
s=get_settings()
validate_production_security(s, AppSessionLocal)
assert backup_encryption_key() is not None, 'Backup encryption key unavailable'
assert Path(s.tts_model_path).is_file(), 'Piper voice unavailable'
assert metadata.version('pypdf') == '6.20.0'
assert metadata.version('Pillow') == '12.3.0'
assert metadata.version('cryptography') == '50.0.2'
print('production isolation, secret mount, dependencies and voice checked')
'''

BACKUP = '''from app.db.session import SessionLocal
from app.services.backup import BackupService
from app.services.backup_crypto import backup_encryption_key, manifest_hmac, sha256_file
from app.models.backup_run import BackupRun
from app.core.config import get_settings
from pathlib import Path
from datetime import datetime,timezone,timedelta
from sqlalchemy import text
import hmac,json,uuid

def verify_preserved_backup(directory,run,key,revision,now):
 assert run.status == "success" and run.kind in {"manual","scheduled"}, "Backup is not successful"
 assert timedelta(0) <= now-run.started_at <= timedelta(minutes=60), "Backup is not recent"
 manifest_path=directory/"manifest.json"
 assert not directory.is_symlink() and not manifest_path.is_symlink(), "Backup path is unsafe"
 manifest=json.loads(manifest_path.read_text())
 assert manifest.get("encrypted") is True and key is not None, "Backup is not encrypted"
 unsigned=dict(manifest);signature=unsigned.pop("hmac_sha256",None)
 assert isinstance(signature,str) and hmac.compare_digest(signature,manifest_hmac(unsigned,key)), "Backup manifest signature is invalid"
 created=datetime.fromisoformat(manifest["created_at"])
 assert run.finished_at is not None and run.started_at-timedelta(seconds=5) <= created <= run.finished_at, "Backup manifest belongs to another run"
 assert manifest["database"]["alembic_revision"] == revision, "Backup schema does not match"
 stamp=manifest["stamp"]
 assert all(location.strip().endswith(chr(92)+stamp) for location in run.location.split(" | ")), "Backup location does not match"
 artifacts=manifest["artifacts"]
 assert len(artifacts)==2 and {a["filename"] for a in artifacts}=={"database.dump.enc","storage.tar.gz.enc"}, "Backup artifacts are incomplete"
 size=manifest_path.stat().st_size
 for artifact in artifacts:
  path=directory/artifact["filename"]
  assert not path.is_symlink() and path.is_file(), "Backup artifact is unavailable"
  assert path.stat().st_size==artifact["size_bytes"] and sha256_file(path)==artifact["sha256"], "Backup artifact is damaged"
  size+=path.stat().st_size
 assert size==run.size_bytes, "Backup size does not match"

with SessionLocal() as db:
 import time
 deadline=time.monotonic()+3600
 while True:
  db.expire_all()
  r=db.get(BackupRun,uuid.UUID("d5135f02-216e-443b-9cba-ccc190faf349"))
  assert r is not None and r.kind=="scheduled", "Expected scheduled backup is unavailable"
  if r.status!="running":break
  db.commit()
  assert time.monotonic()<deadline, "Scheduled backup did not finish in time"
  time.sleep(2)
 assert r.status=="success", "Scheduled pre-rollout backup did not succeed"
 directory=Path(get_settings().storage_path)/".papermind-system/rollout-backup-113"
 verify_preserved_backup(directory,r,backup_encryption_key(),db.scalar(text("SELECT version_num FROM alembic_version")),datetime.now(timezone.utc))
 print(json.dumps({"backup_id":str(r.id),"status":r.status,"bytes":r.size_bytes,"verified_local_copy":True,"adopted_scheduled":True}))
'''

# Copy only this scheduled run's already encrypted artifacts before its normal
# cleanup removes /tmp. Acceptance still waits for successful NAS verification.
BACKUP_COPY = BACKUP[:BACKUP.index('with SessionLocal() as db:')] + '''
import shutil
with SessionLocal() as db:
 r=db.get(BackupRun,uuid.UUID("d5135f02-216e-443b-9cba-ccc190faf349"))
 assert r is not None and r.kind=="scheduled" and r.status in {"running","success"}, "Expected backup is unavailable"
 key=backup_encryption_key();assert key is not None
 matching=[]
 for source in Path("/tmp").glob("pm-backup-*"):
  manifest_path=source/"manifest.json"
  if source.is_symlink() or not manifest_path.is_file() or manifest_path.is_symlink():continue
  manifest=json.loads(manifest_path.read_text());created=datetime.fromisoformat(manifest["created_at"])
  if created<r.started_at-timedelta(seconds=5) or created>datetime.now(timezone.utc):continue
  unsigned=dict(manifest);signature=unsigned.pop("hmac_sha256",None)
  assert manifest.get("encrypted") is True and isinstance(signature,str) and hmac.compare_digest(signature,manifest_hmac(unsigned,key)), "Backup manifest is invalid"
  assert manifest["database"]["alembic_revision"]=="113_drop_note_favorite", "Scheduled backup schema differs"
  artifacts=manifest["artifacts"]
  assert len(artifacts)==2 and {a["filename"] for a in artifacts}=={"database.dump.enc","storage.tar.gz.enc"}
  matching.append((source,manifest,manifest_path.read_bytes()))
 assert len(matching)==1, "Exactly one matching encrypted snapshot is required"
 source,manifest,manifest_bytes=matching[0]
 destination=Path(get_settings().storage_path)/".papermind-system/rollout-backup-113"
 assert not destination.is_symlink()
 destination.mkdir(parents=True,exist_ok=True,mode=0o700)
 for artifact in manifest["artifacts"]:
  original=source/artifact["filename"]
  assert not original.is_symlink() and original.stat().st_size==artifact["size_bytes"]
  temporary=destination/("."+artifact["filename"]+".copying")
  shutil.copy2(original,temporary);temporary.chmod(0o600)
  assert sha256_file(temporary)==artifact["sha256"], "Copied recovery file is damaged"
  temporary.replace(destination/artifact["filename"])
 path=destination/"manifest.json";path.write_bytes(manifest_bytes);path.chmod(0o600)
 print(json.dumps({"copied_backup_id":str(r.id),"encrypted_artifacts":2}))
'''

GUARD = '''from app.services.maintenance import maintenance_mode,system_state_dir
from pathlib import Path
import time
p=system_state_dir()/"rollout-guard"
p.mkdir(parents=True,exist_ok=True)
(p/"stop").unlink(missing_ok=True)
(p/"ready").unlink(missing_ok=True)
with maintenance_mode("application_rollout"):
 (p/"ready").touch()
 try:
  deadline=time.monotonic()+1800
  while not (p/"stop").exists():
   if time.monotonic()>deadline: raise RuntimeError("Rollout maintenance exceeded deadline")
   time.sleep(1)
 finally:
  (p/"ready").unlink(missing_ok=True)
'''

READY = 'from app.services.maintenance import system_state_dir; assert (system_state_dir()/"rollout-guard/ready").is_file()'
RELEASE = 'from app.services.maintenance import system_state_dir; (system_state_dir()/"rollout-guard/stop").touch()'
REVISION = 'from app.db.session import SessionLocal; from sqlalchemy import text;\nwith SessionLocal() as db: print(db.scalar(text("SELECT version_num FROM alembic_version")))'
VERIFY = '''from app.db.session import AppSessionLocal,SessionLocal
from app.core.production import validate_production_security
from app.core.config import get_settings
from sqlalchemy import text,select
from app.models.note import Note
import urllib.request
validate_production_security(get_settings(),AppSessionLocal)
with SessionLocal() as db:
 assert db.scalar(text("SELECT version_num FROM alembic_version")) == "113_drop_note_favorite"
 assert db.scalar(text("SELECT count(*) FROM pg_indexes WHERE indexname='ix_doc_chunks_search_vector'")) == 1
 owner=db.scalar(text("SELECT id FROM users WHERE is_active ORDER BY id LIMIT 1"))
if owner:
 with AppSessionLocal() as db:
  db.info['owner_id']=str(owner)
  db.execute(select(Note.id,Note.pinned_at).limit(1)).all()
assert urllib.request.urlopen("http://127.0.0.1:8040/health/ready",timeout=10).status==200
print('health, schema, chunk index and owner-scoped note query checked')
'''


def run_rollout():
    state = json.loads(STATE.read_text())
    run = CONTROL / 'runs' / state['run_id']
    source = run / 'source'
    names = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    old_path, new_path = run / 'previous-compose.json', run / 'candidate-compose.json'
    guard = 'papermind-rollout-guard'
    guard_started = False
    switching = False
    published_source = False
    old_revision = None
    try:
        update('checking_production', status='running', pid=os.getpid())
        if command(['git', 'rev-parse', 'HEAD'], log=False).strip() not in KNOWN_BASE_COMMITS:
            raise RuntimeError('Production base commit changed since preparation')
        if shutil.disk_usage(ROOT).free < 5 * 1024**3:
            raise RuntimeError('At least 5 GiB free space is required for build and recovery')
        old = read_config(ROOT)
        default_tags = {}
        candidate = read_config(source)
        for service in SERVICES:
            container = command(['docker','compose','--env-file','.env.prod','-f','docker-compose.prod.yml','ps','-q',service],log=False).strip()
            if not container:
                raise RuntimeError('Missing live service: ' + service)
            image = command(['docker','inspect','--format','{{.Image}}',container],log=False).strip()
            default_tags[service] = f'papermind-{service}:latest'
            tag = f'papermind-rollback-{service}:{state["run_id"]}'
            command(['docker','tag',image,tag],log=False)
            old['services'][service].pop('build',None)
            old['services'][service]['image']=tag
            context = source if service == 'worker' else source / service
            candidate['services'][service]['build']['context']=str(context)
            if service in {'backend','worker'} and (source/service/'Dockerfile.rollout').exists():
                candidate['services'][service]['build']['dockerfile']='worker/Dockerfile.rollout' if service=='worker' else 'Dockerfile.rollout'
            candidate['services'][service]['image']=f'papermind-release-{service}:{ARCHIVE_SHA256[:16]}'
        for service in ('backend','worker'):
            candidate['services'][service]['environment']['APP_REVISION']='snapshot:' + ARCHIVE_SHA256[:16]
        atomic_json(old_path,old);atomic_json(new_path,candidate)
        save_and_publish(source,names,run)
        for service in SERVICES:
            update('building_' + service)
            compose(new_path,'build',service,timeout=3600)
        update('preflight')
        compose(new_path,'run','--rm','--no-deps','backend','python','-c',PREFLIGHT,timeout=180)
        old_revision = compose(old_path,'exec','-T','backend','python','-c',REVISION,log=False).strip()
        if not re.fullmatch(r'[0-9]{3}_[a-z0-9_]+',old_revision) or not (source / f'backend/alembic/versions/{old_revision}.py').exists():
            raise RuntimeError('Production migration revision is not supported by the release')
        atomic_json(run / 'database-before.json',{'revision':old_revision})
        if command(['git','rev-parse','HEAD'],log=False).strip() not in KNOWN_BASE_COMMITS:
            raise RuntimeError('Production changed during the image build')
        update('copying_existing_backup')
        compose(old_path,'exec','-T','worker','python','-c',BACKUP_COPY,timeout=180)
        update('backup')
        backup = compose(old_path,'run','--rm','--no-deps','--name','papermind-rollout-backup','backend','python','-c',BACKUP,timeout=3600)
        backup_result=json.loads(backup.strip().splitlines()[-1])
        update('draining_writes',backup=backup_result)
        compose(old_path,'run','-d','--no-deps','--name',guard,'backend','python','-c',GUARD,log=False)
        guard_started=True
        deadline=time.monotonic()+960
        while True:
            try:
                command(['docker','exec',guard,'python','-c',READY],log=False,timeout=10)
                break
            except RuntimeError:
                if time.monotonic()>deadline: raise RuntimeError('Writes did not drain')
                time.sleep(2)
        if command(['git','rev-parse','HEAD'],log=False).strip() not in KNOWN_BASE_COMMITS:
            raise RuntimeError('Production changed before switching')
        switching=True
        compose(old_path,'stop','worker',timeout=180)
        update('migrating')
        compose(new_path,'run','--rm','--no-deps','backend','alembic','upgrade','head',timeout=900)
        for service in SERVICES:
            command(['docker','tag',candidate['services'][service]['image'],default_tags[service]],log=False)
        update('publishing_source')
        published_source=True
        save_and_publish(source,names,run,publish=True)
        update('starting_services')
        compose(new_path,'up','-d','--no-build','--no-deps','--wait','--wait-timeout','180','ai','backend','frontend',timeout=240)
        compose(new_path,'exec','-T','backend','python','-c',VERIFY,timeout=60)
        compose(new_path,'up','-d','--no-build','--no-deps','--wait','--wait-timeout','180','worker',timeout=240)
        compose(new_path,'exec','-T','caddy','caddy','reload','--config','/etc/caddy/Caddyfile',timeout=30)
        atomic_json(CONTROL/'installed.json',{'archive_sha256':ARCHIVE_SHA256,'revision':TARGET_REVISION,'run_id':state['run_id']})
        update('complete',status='success',schema_revision=TARGET_REVISION)
    except Exception as exc:
        print(scrub(str(exc)),flush=True)
        rollback_ok = not switching
        if switching:
            update('rolling_back',status='running',error=scrub(str(exc))[:3000])
            try:
                compose(new_path,'stop','worker','backend','frontend',timeout=180)
                compose(new_path,'run','--rm','--no-deps','backend','alembic','downgrade',old_revision,timeout=900)
                if published_source: restore_source(run)
                for service in SERVICES:
                    command(['docker','tag',old['services'][service]['image'],default_tags[service]],log=False)
                compose(old_path,'up','-d','--no-build','--no-deps','--wait','--wait-timeout','180','ai','backend','frontend','worker',timeout=300)
                compose(old_path,'exec','-T','caddy','caddy','reload','--config','/etc/caddy/Caddyfile',timeout=30)
                rollback_ok=True
            except Exception as rollback:
                print(scrub('Rollback failed: '+str(rollback)),flush=True)
        update('failed',status='failed',error=scrub(str(exc))[:3000],rollback_ok=rollback_ok)
    finally:
        if guard_started:
            command(['docker','exec',guard,'python','-c',RELEASE],log=False,check=False,timeout=10)
            time.sleep(2)
            command(['docker','rm','-f',guard],log=False,check=False,timeout=30)


def start(raw):
    archive=load_release(raw)
    if not (ROOT/'.git').exists() or not (ROOT/'.env.prod').is_file():
        raise ValueError('Fixed production checkout is unavailable')
    CONTROL.mkdir(parents=True,exist_ok=True);CONTROL.chmod(0o700)
    with (CONTROL/'admission.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if STATE.exists():
            previous=json.loads(STATE.read_text())
            if previous.get('status')=='running':
                try:
                    pid=int(previous.get('pid',0))
                    if pid <= 0: raise ValueError('Rollout process is starting')
                    os.kill(pid,0)
                except ProcessLookupError: pass
                else: raise ValueError('A rollout is already running')
            if previous.get('status')=='success' and previous.get('archive_sha256')==ARCHIVE_SHA256:
                print(json.dumps(previous));return
        run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+ARCHIVE_SHA256[:12]
        run=CONTROL/'runs'/run_id;run.mkdir(parents=True,mode=0o700)
        source=run/'source';source.mkdir(mode=0o700)
        unpack(archive,source)
        atomic_json(STATE,{'status':'running','phase':'starting','run_id':run_id,'archive_sha256':ARCHIVE_SHA256})
        runner=CONTROL/'runner.py';runner.write_text(Path(__file__).read_text());runner.chmod(0o700)
        with LOG.open('w') as log:
            LOG.chmod(0o600)
            process=subprocess.Popen([sys.executable,str(runner),'--run'],cwd=ROOT,stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        print(json.dumps({'status':'started','run_id':run_id,'pid':process.pid}))


def status():
    state=json.loads(STATE.read_text()) if STATE.exists() else {'status':'not_started'}
    print(json.dumps(state))
    if LOG.exists():print(LOG.read_text(errors='replace')[-8000:])


def main():
    if sys.argv[1:]==['--run']:run_rollout()
    elif sys.argv[1:]==['--status']:status()
    elif not sys.argv[1:]:start(sys.stdin.read(12*1024*1024+1))
    else:raise ValueError('Unsupported fixed rollout operation')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(scrub(str(exc)),file=sys.stderr)
        sys.exit(1)
