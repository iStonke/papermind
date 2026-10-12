#!/usr/bin/env python3
"""Fixed release reboot, inert until its separate bridge action is authorized."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pi_security_patch as release

STATE = release.CONTROL / 'restart-state.json'
HOST_STATE = release.CONTROL / 'host-state.json'
HOST_SCRIPT = release.ROOT / 'deploy/host-control/papermind-host-control.sh'
HOST_SCRIPT_SHA256 = '984b63da3c0c5eb9f756b123a3e5723b98ddb05bab3f8e6cbf7f6bbc46ef13f1'

CHECK = '''from app.db.session import SessionLocal
from app.services.maintenance import is_maintenance_active
from app.services.system_status import _power_available,_pending_action,_command_path
from sqlalchemy import text
from pathlib import Path
import json,uuid
identifier=BACKUP_ID
with SessionLocal() as db:
 db.execute(text('SET TRANSACTION READ ONLY'))
 row=db.execute(text("SELECT status,extract(epoch from (now()-finished_at))::integer AS age_seconds FROM backup_runs WHERE id=:identifier"),{'identifier':identifier}).mappings().one()
 result={'backup_success':row['status']=='success','backup_age_seconds':row['age_seconds'],
  'active_jobs':db.scalar(text("SELECT count(*) FROM jobs WHERE status IN ('queued','running')")),
  'active_backups':db.scalar(text("SELECT count(*) FROM backup_runs WHERE status='running'")),
  'schema_ok':db.scalar(text('SELECT version_num FROM alembic_version'))=='113_drop_note_favorite'}
path=_command_path()
result.update(power_available=_power_available(),pending_action=_pending_action(),
 command_path_ok=path=='/host/control/command',command_file_present=bool(path and Path(path).exists()),
 maintenance_active=is_maintenance_active())
print(json.dumps(result))
'''


def application_checks(backup_id):
    import uuid
    identifier = str(uuid.UUID(backup_id))
    code = CHECK.replace('identifier=BACKUP_ID', 'identifier=' + repr(identifier))
    output = release.helpers.compose(release.NEW, 'exec', '-T', 'backend', 'python', '-c', code, log=False, timeout=20)
    return json.loads(output.strip().splitlines()[-1])


def control_checks():
    output = subprocess.run(['systemctl', 'show', 'papermind-host-control.service',
        '--property=LoadState', '--property=ActiveState', '--property=User',
        '--property=ExecStart', '--property=Environment'], text=True, capture_output=True, timeout=10)
    fields = dict(line.split('=', 1) for line in output.stdout.splitlines() if '=' in line)
    try:
        script_ok = not HOST_SCRIPT.is_symlink() and hashlib.sha256(HOST_SCRIPT.read_bytes()).hexdigest() == HOST_SCRIPT_SHA256
    except OSError:
        script_ok = False
    return {'service_active':output.returncode == 0 and fields.get('LoadState') == 'loaded' and fields.get('ActiveState') == 'active',
        'service_root':fields.get('User') in ('', 'root'),
        'service_script_ok':str(HOST_SCRIPT) in fields.get('ExecStart', '') and script_ok,
        'service_directory_ok':'CONTROL_DIR=/home/jan/papermind/host-control' in fields.get('Environment', '')}


def validate(checks):
    required = ('service_active','service_root','service_script_ok','service_directory_ok',
        'backup_verified','backup_success','schema_ok','power_available','command_path_ok','host_complete')
    reasons = [name for name in required if checks.get(name) is not True]
    if not isinstance(checks.get('backup_age_seconds'), int) or not 0 <= checks['backup_age_seconds'] <= 86400:
        reasons.append('backup_age_seconds')
    for name in ('active_jobs','active_backups'):
        if checks.get(name) != 0:reasons.append(name)
    for name in ('maintenance_active','command_file_present','pending_action','already_requested'):
        if checks.get(name):reasons.append(name)
    return reasons


def readiness():
    release.preflight(release.TARGET)
    host = json.loads(HOST_STATE.read_text())
    checks = {'host_complete':host.get('status') == 'success',
        'backup_verified':host.get('backup',{}).get('verified_encrypted') is True,
        'already_requested':STATE.exists()}
    checks.update(control_checks())
    checks.update(application_checks(host['backup']['backup_id']))
    reasons = validate(checks)
    return {'ready':not reasons,'checks':checks,'blocking_checks':reasons}


def request():
    # This mode is not registered in the bridge without separate reboot approval.
    with (release.CONTROL / 'restart-admission.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        checked = readiness()
        assert checked['ready'], 'Restart preconditions failed'
        release.helpers.atomic_json(STATE, {'status':'admitted',
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()})
        code = '''from app.services.maintenance import maintenance_mode
from app.services.system_status import request_power_action,_command_path
from app.db.session import SessionLocal
from sqlalchemy import text
from pathlib import Path
import time,json
with maintenance_mode('security_library_activation'):
 with SessionLocal() as db:
  db.execute(text('SET TRANSACTION READ ONLY'))
  assert db.scalar(text("SELECT count(*) FROM jobs WHERE status IN ('queued','running')"))==0
  assert db.scalar(text("SELECT count(*) FROM backup_runs WHERE status='running'"))==0
 assert _command_path()=='/host/control/command' and not Path(_command_path()).exists()
 accepted,_=request_power_action('reboot')
 assert accepted,'Host control rejected reboot'
 print(json.dumps({'status':'reboot_queued'}),flush=True)
 time.sleep(20)
'''
        print(json.dumps({'status':'admitted'}), flush=True)
        # Shutdown may interrupt this exec; the one-shot state survives that.
        output = release.helpers.compose(release.NEW, 'exec', '-T',
            '-e', 'BACKUP_QUIESCE_TIMEOUT_SECONDS=10', 'backend', 'python', '-c', code,
            log=False, check=False, timeout=40)
        print(json.dumps({'host_control_acknowledged':'reboot_queued' in output}), flush=True)


def result():
    if not STATE.exists():return {'requested':False,'boot_changed':False}
    previous=json.loads(STATE.read_text())
    return {'requested':True,'boot_changed':previous['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def main():
    if sys.argv[1:] == ['--ready']:print(json.dumps(readiness()))
    elif sys.argv[1:] == ['--request']:request()
    else:raise ValueError('Unsupported fixed restart operation')


if __name__ == '__main__':main()
