#!/usr/bin/env python3
"""Fixed security release: staged build, fresh backup, UID migration and rollback.

The bridge pins this program, its helper and the release payload; no user
parameters, environment values, image names, source refs or hosts are accepted.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pi_rollout as helpers
import pi_audit as inventory_helpers
from audit_pi_packages import package_fingerprints

ROOT = Path('/home/jan/papermind')
CONTROL = ROOT / '.runtime/pi-security-patch'
BASE = 'acc22ca29a695cdd987624b479d90aa7aed419a3'
TARGET = '01d1c53ba38f68857674238ef7643534987f3018'
ARCHIVE_SHA256 = '1fd05022e17d55df664de78c80c2e0c9a61aa32f0c2ab7d4751f53450176ec30'
APPROVED_PACKAGES = {'backend': '56188f1e900f57cd9059a2ac4bfbdf1ee0a7d6ba1dc0f0c84fe752c178696b5d', 'worker': 'c6e3cf37761439dffb9570656d372615e54a7aae9e8add5190574dfcffb78d7a', 'ai': 'a3993f4746bba33dd57e67f06842624e5c8da265cdb471a20da65ae437093937', 'frontend': 'd93d708ce8c5bcaa35731ff76192caafdfaa8944d86faf204a5370d29f7b3810', 'db': '3f4d3f54111a89c31d7720f17b94b6b505eadc5a636a434825731997665242ac', 'caddy': 'e1fb7dd58fefe12c0e3eb88fe18e06c32e8551e00113aebf9a5fb71f2f2320f2', 'caddy-go': '1b166525a9c62b42cc7bb434f9d3f10773adab108b0f47f172c970bd2c217f1a'}
SERVICES = ('db', 'ai', 'backend', 'frontend', 'caddy', 'worker')
STATE = CONTROL / 'release-state.json'
SOURCE = CONTROL / 'source'
OLD = CONTROL / 'previous-compose.json'
NEW = CONTROL / 'candidate-compose.json'


def update(phase, **fields):
    value = json.loads(STATE.read_text()) if STATE.exists() else {}
    value.update(phase=phase, **fields)
    helpers.atomic_json(STATE, value)
    print(phase, flush=True)


def preflight(expected=BASE):
    assert helpers.command(['git', 'rev-parse', 'HEAD'], log=False).strip() == expected, 'Pi source revision changed'
    assert not helpers.command(['git', 'status', '--porcelain', '--untracked-files=no'], log=False).strip(), 'Tracked source changed'
    assert os.getuid() == 1000 and os.getgid() == 1000, 'Private mount identity differs'
    result = {}
    for name in SERVICES:
        identifier = helpers.command(['docker','compose','--env-file','.env.prod','-f','docker-compose.prod.yml','ps','-q',name],log=False).strip()
        assert identifier, 'Missing service: ' + name
        data = json.loads(helpers.command(['docker','inspect','--format','{{json .State}}',identifier],log=False))
        assert data['Running'] and data.get('Health',{}).get('Status','healthy') == 'healthy', 'Unhealthy service: ' + name
        result[name] = {'container': identifier, 'image': helpers.command(['docker','inspect','--format','{{.Image}}',identifier],log=False).strip()}
    return result


BACKUP = '''from app.db.session import SessionLocal
from app.services.backup import BackupService
from app.services.backup_crypto import backup_encryption_key,manifest_hmac,sha256_file
from pathlib import Path
import hmac,json
directory=Path('/data/storage/.papermind-system/security-patch-backup-20261012')
with SessionLocal() as db:
 r=BackupService(db).run_backup(kind='manual',apply_retention=False,preserve_to=directory)
 assert r.status=='success','Fresh backup failed'
 manifest=json.loads((directory/'manifest.json').read_text())
 unsigned=dict(manifest);signature=unsigned.pop('hmac_sha256')
 key=backup_encryption_key();assert key is not None and manifest['encrypted'] is True
 assert hmac.compare_digest(signature,manifest_hmac(unsigned,key))
 assert manifest['database']['alembic_revision']=='113_drop_note_favorite'
 for artifact in manifest['artifacts']:
  path=directory/artifact['filename']
  assert not path.is_symlink() and path.stat().st_size==artifact['size_bytes'] and sha256_file(path)==artifact['sha256']
 print(json.dumps({'backup_id':str(r.id),'bytes':r.size_bytes,'verified_encrypted':True}))
'''

# Filesystem ownership metadata stays private on the Pi. No contents are read.
OWNERSHIP = '''import json,os,stat
from pathlib import Path
roots=[Path('/data/storage')]
manifest=Path('/ownership/metadata.json')
rows=[]
for root in roots:
 for parent,dirs,files in os.walk(root,followlinks=False):
  for path in [Path(parent),*[Path(parent)/n for n in dirs+files]]:
   relative=str(path.relative_to(root));info=path.lstat()
   assert info.st_uid in {0,1000},'Unknown storage owner'
   assert not info.st_mode & stat.S_ISUID and not (stat.S_ISREG(info.st_mode) and info.st_mode & stat.S_ISGID),'Unexpected special permissions'
   rows.append([relative,info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode)])
   assert len(rows)<=200000,'Ownership metadata bound'
manifest.write_text(json.dumps(rows));manifest.chmod(0o600)
for relative,uid,gid,mode in rows:
 os.chown(roots[0]/relative,1000,1000,follow_symlinks=False)
 if not (roots[0]/relative).is_symlink():os.chmod(roots[0]/relative,mode)
print(json.dumps({'ownership_entries':len(rows)}))
'''

RESTORE_OWNERSHIP = '''import json,os
from pathlib import Path
root=Path('/data/storage')
for relative,uid,gid,mode in json.loads(Path('/ownership/metadata.json').read_text()):
 path=root/relative
 if path.exists() or path.is_symlink():
  os.chown(path,uid,gid,follow_symlinks=False)
  if not path.is_symlink():os.chmod(path,mode)
'''


def prepare():
    before = preflight()
    assert helpers.shutil.disk_usage(ROOT).free >= 10 * 1024**3, 'Insufficient build/backup space'
    old = helpers.read_config(ROOT)
    new = helpers.read_config(SOURCE)
    contexts = {'db': SOURCE/'deploy/db', 'caddy': SOURCE/'deploy/caddy', 'worker': SOURCE,
                'backend': SOURCE/'backend', 'ai': SOURCE/'ai', 'frontend': SOURCE/'frontend'}
    for name in SERVICES:
        old['services'][name].pop('build',None)
        old['services'][name]['image'] = before[name]['image']
        new['services'][name]['build']['context'] = str(contexts[name])
        new['services'][name]['image'] = 'papermind-security-' + name + ':' + TARGET[:12]
        if name in ('backend','worker'):
            new['services'][name]['environment']['APP_REVISION'] = TARGET
    helpers.atomic_json(OLD,old);helpers.atomic_json(NEW,new)
    ca = helpers.command(['docker','exec',before['caddy']['container'],'sha256sum','/data/caddy/pki/authorities/local/root.crt'],log=False).split()[0]
    helpers.atomic_json(CONTROL/'original-ca.json',{'sha256':ca})
    db_checks = '''from app.db.session import SessionLocal
from sqlalchemy import text
import json
with SessionLocal() as db:
 db.execute(text('SET TRANSACTION READ ONLY'))
 extensions=dict(db.execute(text('SELECT extname,extversion FROM pg_extension')).all())
 assert set(extensions)<={'plpgsql','vector','pgcrypto','pg_trgm'},'Extension migration requires review'
 assert db.scalar(text("SELECT count(*) FROM pg_replication_slots WHERE plugin NOT IN ('pgoutput','test_decoding')"))==0,'Logical plugin migration requires review'
 version=db.scalar(text('SHOW server_version_num'));assert 170000<=int(version)<180000
 collation=db.execute(text('SELECT datcollversion,pg_database_collation_actual_version(oid) FROM pg_database WHERE datname=current_database()')).one()
 assert collation[0] is None or collation[0]==collation[1],'Existing collation requires reindexing'
 print(json.dumps({'extensions':extensions,'server_version_num':version,'collation':list(collation)}))
'''
    database=json.loads(helpers.compose(OLD,'exec','-T','backend','python','-c',db_checks,log=False).strip().splitlines()[-1])
    helpers.atomic_json(CONTROL/'database-before.json',database)
    update('building',status='running',before=before)
    for name in SERVICES:
        update('building_' + name)
        helpers.compose(NEW,'build',name,timeout=3600)
    # The production UID can read the existing 0600 backup key; no candidate
    # receives application writes before the ownership migration.
    helpers.compose(NEW,'run','--rm','--no-deps','backend','python','-c',helpers.PREFLIGHT,timeout=180)
    helpers.compose(NEW,'run','--rm','--no-deps','--user','0:0','caddy','caddy','validate','--config','/etc/caddy/Caddyfile',timeout=60)
    assert preflight() == before, 'Production containers changed while preparing'
    update('prepared',status='prepared')


def change_ownership(old, *, restore=False):
    # Only fixed app volumes and the frontend asset directory are mounted.
    targets = [('storage','backend','/data/storage'),('models','ai','/models'),
               ('assets','frontend','/usr/share/nginx/html/assets'),('caddy-data','caddy','/data'),('caddy-config','caddy','/config')]
    for label,service,destination in targets:
        folder = CONTROL / 'ownership' / label;folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        manifest = folder/'metadata.json'
        if restore and not manifest.exists():continue
        mounts = [volume for volume in old['services'][service]['volumes'] if volume['target'] == destination]
        assert len(mounts) == 1
        mount = mounts[0]
        if mount['type'] == 'volume':
            source = old['volumes'][mount['source']]['name']
        else:
            source = mount['source']
            assert Path(source).resolve() == (ROOT/'.runtime/frontend-assets').resolve()
        program = RESTORE_OWNERSHIP if restore else OWNERSHIP
        helpers.command(['docker','run','--rm','--network','none','--user','0:0','--entrypoint','python',
            '-v',source+':/data/storage','-v',str(folder)+':/ownership',old['services']['backend']['image'],
            '-c',program],timeout=300)


def candidate_inventory():
    state = json.loads(STATE.read_text())
    assert state['status'] == 'prepared' and preflight() == state['before']
    config = json.loads(NEW.read_text())
    result = {'collected_at':helpers.datetime.now(helpers.timezone.utc).isoformat(), 'head':TARGET,
        'kernel':helpers.command(['uname','-r'],log=False).strip(), 'targets':{}}
    for name in SERVICES:
        image = config['services'][name]['image']
        def run(*args, check=True):
            return helpers.command(['docker','run','--rm','--network','none','--entrypoint',args[0],image,*args[1:]],log=False,check=check,timeout=90)
        entry = {'os_release':run('cat','/etc/os-release'),
            'image':helpers.command(['docker','image','inspect','--format','{{.Id}}',image],log=False).strip()}
        if 'ID=alpine' in entry['os_release']:
            entry.update(manager='apk',apk_database=run('cat','/lib/apk/db/installed'))
        else:
            entry.update(manager='dpkg',packages=inventory_helpers.parse_dpkg(run('dpkg-query','-W','-f='+inventory_helpers.DPKG_FORMAT)))
        entry['runtime_versions']={}
        if name=='caddy':entry['runtime_versions']['caddy']=run('caddy','build-info')
        result['targets'][name]=entry
    assert len(json.dumps(result).encode())<900000
    helpers.atomic_json(CONTROL/'candidate-inventory.json',result)
    print(json.dumps(result))


def apply():
    state = json.loads(STATE.read_text())
    assert state['status'] == 'running' and state['phase'] == 'starting_apply', 'Release not admitted'
    assert preflight() == state['before'], 'Prepared production state changed'
    old = json.loads(OLD.read_text())
    new = json.loads(NEW.read_text())
    for config in (old,new):
        for service in config['services'].values():
            for key,value in service.get('environment',{}).items():
                if value and any(term in key.upper() for term in ('PASSWORD','SECRET','TOKEN','KEY','DATABASE_URL')):
                    helpers._redactions.add(str(value))
    inventory = json.loads((CONTROL/'candidate-inventory.json').read_text())
    assert inventory['head']==TARGET
    assert package_fingerprints(inventory)==APPROVED_PACKAGES, 'Candidate packages differ from the audited versions'
    for name in SERVICES:
        assert helpers.command(['docker','image','inspect','--format','{{.Id}}',new['services'][name]['image']],log=False).strip() == inventory['targets'][name]['image'], 'Candidate image changed after inventory'
    switched = False
    changed_ownership = False
    git_changed = False
    guard = 'papermind-security-patch-guard'
    guard_started = False
    try:
        update('backup',status='running')
        backup = helpers.compose(OLD,'run','--rm','--no-deps','--user','0:0','backend','python','-c',BACKUP,timeout=3600)
        update('draining_writes',backup=json.loads(backup.strip().splitlines()[-1]))
        helpers.compose(OLD,'run','-d','--no-deps','--name',guard,'backend','python','-c',helpers.GUARD,log=False)
        guard_started = True
        deadline = time.monotonic() + 960
        while True:
            try:
                helpers.command(['docker','exec',guard,'python','-c',helpers.READY],log=False,timeout=10);break
            except RuntimeError:
                assert time.monotonic() < deadline, 'Writes did not drain'
                time.sleep(2)
        assert preflight() == state['before'], 'Production changed before switching'
        helpers.command(['git','fetch','--no-tags','origin','feat/ki-chat-integration'],log=False)
        assert helpers.command(['git','rev-parse',TARGET],log=False).strip() == TARGET
        helpers.command(['git','merge-base','--is-ancestor',BASE,TARGET],log=False)
        update('stopping_services')
        switched = True
        helpers.compose(OLD,'stop','worker','backend','frontend','caddy','ai',timeout=180)
        update('migrating_ownership')
        changed_ownership = True
        change_ownership(old)
        helpers.command(['git','merge','--ff-only',TARGET],log=False)
        git_changed = True
        update('updating_database')
        helpers.compose(OLD,'stop','db',timeout=180)
        helpers.compose(NEW,'up','-d','--no-build','--no-deps','--wait','--wait-timeout','180','db',timeout=240)
        update('starting_services')
        helpers.compose(NEW,'up','-d','--no-build','--no-deps','--wait','--wait-timeout','180','ai','backend','frontend','caddy',timeout=300)
        helpers.compose(NEW,'exec','-T','backend','python','-c',helpers.VERIFY,timeout=60)
        vector_check="from app.db.session import SessionLocal;from sqlalchemy import text;\nwith SessionLocal() as db:\n assert db.scalar(text(\"SELECT ('[1,2]'::vector <-> '[1,2]'::vector)=0\"));a=db.execute(text('SELECT datcollversion,pg_database_collation_actual_version(oid) FROM pg_database WHERE datname=current_database()')).one();assert a[0] is None or a[0]==a[1]"
        helpers.compose(NEW,'exec','-T','backend','python','-c',vector_check,timeout=60)
        helpers.compose(NEW,'up','-d','--no-build','--no-deps','--wait','--wait-timeout','180','worker',timeout=240)
        running=preflight(TARGET)
        ca=helpers.command(['docker','exec',running['caddy']['container'],'sha256sum','/data/caddy/pki/authorities/local/root.crt'],log=False).split()[0]
        assert ca==json.loads((CONTROL/'original-ca.json').read_text())['sha256'], 'Existing TLS CA changed'
        for name in SERVICES:
            helpers.command(['docker','tag',new['services'][name]['image'],'papermind-'+name+':latest'],log=False)
        helpers.atomic_json(CONTROL/'installed.json',{'archive_sha256':ARCHIVE_SHA256,'head':TARGET,'schema':'113_drop_note_favorite'})
        update('complete',status='success',head=TARGET)
    except Exception as exc:
        rollback_ok = not switched
        if switched:
            update('rolling_back',error_type=type(exc).__name__)
            try:
                helpers.compose(NEW,'stop',*reversed(SERVICES),timeout=240)
                if changed_ownership:change_ownership(old,restore=True)
                if git_changed:
                    assert helpers.command(['git','rev-parse','HEAD'],log=False).strip() == TARGET
                    assert not helpers.command(['git','status','--porcelain','--untracked-files=no'],log=False).strip()
                    helpers.command(['git','reset','--hard',BASE],log=False)
                helpers.compose(OLD,'up','-d','--no-build','--no-deps','--wait','--wait-timeout','180',*SERVICES,timeout=300)
                preflight();rollback_ok = True
            except Exception as rollback:
                print('Rollback failed: ' + type(rollback).__name__,flush=True)
        update('failed',status='failed',error_type=type(exc).__name__,rollback_ok=rollback_ok)
        raise
    finally:
        if guard_started:
            helpers.command(['docker','exec',guard,'python','-c',helpers.RELEASE],log=False,check=False,timeout=10)
            time.sleep(2)
            helpers.command(['docker','rm','-f',guard],log=False,check=False,timeout=30)


def start(mode):
    CONTROL.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (CONTROL/'release.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        previous = json.loads(STATE.read_text()) if STATE.exists() else {}
        assert previous.get('status') not in {'running','success'}, 'Release already active or complete'
        if mode == 'prepare':
            payload = json.loads(sys.stdin.read(12*1024*1024+1))
            assert set(payload)=={'archive_base64','archive_sha256'} and payload['archive_sha256']==ARCHIVE_SHA256
            archive = base64.b64decode(payload['archive_base64'],validate=True)
            assert hashlib.sha256(archive).hexdigest()==ARCHIVE_SHA256
            assert len(archive)<=helpers.MAX_ARCHIVE_BYTES
            preflight()
            SOURCE.mkdir(parents=True,exist_ok=True,mode=0o700)
            helpers.unpack(archive,SOURCE)
        if mode=='apply':assert previous.get('status')=='prepared'
        update('starting_'+mode,status='running')
        with (CONTROL/'release.log').open('w') as log:
            os.chmod(log.name,0o600)
            process = subprocess.Popen([sys.executable,__file__,'--run-'+mode],cwd=ROOT,stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        print(json.dumps({'status':'started','pid':process.pid,'mode':mode}))


def backup_progress(*, installed=False):
    """Only bounded, numeric progress; never backup paths, bodies or errors."""
    program = '''from app.db.session import SessionLocal
from sqlalchemy import text
from pathlib import Path
import json,os
with SessionLocal() as db:
 db.execute(text('SET TRANSACTION READ ONLY'))
 row=db.execute(text("SELECT status,extract(epoch from (now()-started_at))::integer AS age_seconds FROM backup_runs ORDER BY started_at DESC LIMIT 1")).mappings().first()
 result={'latest_backup':dict(row) if row else None,'running_jobs':db.scalar(text("SELECT count(*) FROM jobs WHERE status='running'"))}
files=0;total=0
for folder in list(Path('/tmp').glob('pm-backup-*'))[:20]:
 if folder.is_symlink() or not folder.is_dir():continue
 for path in list(folder.iterdir())[:20]:
  if not path.is_symlink() and path.is_file():files+=1;total+=path.stat().st_size
result.update(temporary_artifacts=files,temporary_bytes=total)
network=[line.split(':',1)[1].split() for line in Path('/proc/net/dev').read_text().splitlines() if ':' in line and line.split(':',1)[0].strip()!='lo']
result.update(network_received_bytes=sum(int(n[0]) for n in network),network_sent_bytes=sum(int(n[8]) for n in network))
process=Path('/proc/1/stat').read_text().rsplit(') ',1)[1].split()
result['process_cpu_seconds']=round((int(process[11])+int(process[12]))/os.sysconf('SC_CLK_TCK'),2)
print(json.dumps(result))
'''
    try:
        if installed:
            value = helpers.compose(NEW,'exec','-T','backend','python','-c',program,log=False,timeout=20)
        else:
            identifiers = helpers.command(['docker','ps','--filter','label=com.docker.compose.project=papermind',
                '--filter','label=com.docker.compose.service=backend',
                '--filter','label=com.docker.compose.oneoff=True','--format','{{.ID}}'],log=False).split()
            assert len(identifiers) == 1, 'Backup container selection differs'
            value = helpers.command(['docker','exec',identifiers[0],'python','-c',program],
                log=False, timeout=20)
        print(json.dumps({'backup_progress':json.loads(value.strip().splitlines()[-1])}))
    except Exception as exc:
        print(json.dumps({'backup_progress_error':type(exc).__name__}))


def main():
    if sys.argv[1:] == ['--prepare']:start('prepare')
    elif sys.argv[1:] == ['--apply']:start('apply')
    elif sys.argv[1:] == ['--run-prepare']:prepare()
    elif sys.argv[1:] == ['--run-apply']:apply()
    elif sys.argv[1:] == ['--inventory']:candidate_inventory()
    elif sys.argv[1:] == ['--status']:
        print(STATE.read_text() if STATE.exists() else '{"status":"not_started"}')
        if STATE.exists() and json.loads(STATE.read_text()).get('phase') == 'backup':backup_progress()
        if (CONTROL/'release.log').exists():print((CONTROL/'release.log').read_text(errors='replace')[-8000:])
    else:raise ValueError('Unsupported fixed security release operation')


if __name__ == '__main__':
    try:main()
    except Exception as exc:
        if sys.argv[1:] in (['--run-prepare'],['--run-apply']):
            update('failed',status='failed',error_type=type(exc).__name__)
        print(type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
