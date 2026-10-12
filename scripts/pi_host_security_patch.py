#!/usr/bin/env python3
"""Fixed, separately staged host security package updates; never reboots."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pi_security_patch as release

STATE=release.CONTROL/'host-state.json'
PLAN=release.CONTROL/'host-plan.json'


def progress(phase,**fields):
    value=json.loads(STATE.read_text()) if STATE.exists() else {}
    value.update(status='running',phase=phase,**fields)
    release.helpers.atomic_json(STATE,value)


def installed():
    return release.helpers.command(['dpkg-query','-W','-f=${binary:Package}\t${Version}\t${db:Status-Abbrev}\n'],log=False)


def parse_plan(output):
    assert not any(line.startswith('Remv ') for line in output.splitlines()), 'Package removal is forbidden'
    packages=[]
    for line in output.splitlines():
        if line.startswith('Inst '):
            match=re.match(r'^Inst ([a-z0-9][a-z0-9+.:~-]*) (?:\[([^\]]+)\] )?\((\S+)',line)
            assert match is not None, 'Unrecognized package plan'
            name,old,new=match.groups()
            assert old is not None, 'New packages require separate review'
            assert not name.startswith(('linux-','raspi','rpi-','docker','containerd','systemd','openssh')), 'Unexpected system transition'
            packages.append({'name':name,'old':old,'new':new})
    assert len(packages)<=200, 'Package plan bound'
    return packages


def apt(action,timeout=900):
    assert action in {'update','plan','download','verify','install'}
    result=subprocess.run(['sudo','-n','/usr/local/libexec/papermind-security-20261012',action],cwd=release.ROOT,
        text=True,capture_output=True,timeout=timeout)
    with (release.CONTROL/'host-apt.log').open('a') as log:
        os.chmod(log.name,0o600);log.write(result.stdout+result.stderr)
    assert result.returncode==0, 'Fixed APT operation failed'
    return result.stdout


def plan():
    state=json.loads(release.STATE.read_text())
    if state.get('status')=='success':
        release.preflight(release.TARGET)
    else:
        # Metadata/download preparation can overlap the verified release backup.
        # Installation below still requires the successfully installed target.
        assert state.get('status')=='running' and state.get('phase')=='backup', 'Release staging phase differs'
        release.preflight(release.BASE)
    names=json.loads(Path(__file__).with_name('pi_host_security_packages.json').read_text())
    assert len(names)==103 and all(re.fullmatch(r'[a-z0-9][a-z0-9+.-]*',name) for name in names)
    before=installed()
    installed_names={line.split('\t')[0].split(':')[0] for line in before.splitlines()
        if len(line.split('\t'))==3 and line.split('\t')[2][1:2]=='i'}
    assert set(names)<=installed_names, 'Audited package selection changed'
    progress('updating_package_indexes')
    apt('update')
    progress('simulating_package_plan')
    packages=parse_plan(apt('plan'))
    pins=[p['name']+'='+p['new'] for p in packages]
    if pins:
        progress('downloading_packages',updates=len(packages))
        apt('download')
    value={'head':release.TARGET,'installed_sha256':hashlib.sha256(before.encode()).hexdigest(),'packages':packages}
    release.helpers.atomic_json(PLAN,value)
    release.helpers.atomic_json(STATE,{'status':'prepared','phase':'host_prepared','updates':len(packages)})


def apply():
    release.preflight(release.TARGET)
    value=json.loads(PLAN.read_text())
    assert json.loads(STATE.read_text())['phase']=='starting_apply'
    assert value['head']==release.TARGET and hashlib.sha256(installed().encode()).hexdigest()==value['installed_sha256'], 'Host package state changed'
    pins=[p['name']+'='+p['new'] for p in value['packages']]
    if pins:
        progress('verifying_package_plan',updates=len(pins))
        simulated=parse_plan(apt('verify'))
        assert sorted(simulated,key=lambda p:p['name'])==sorted(value['packages'],key=lambda p:p['name']), 'APT plan changed'
        # Preserve a second encrypted recovery copy without replacing rollout backup.
        backup=release.BACKUP.replace('security-patch-backup-20261012','security-host-backup-20261012')
        progress('backup')
        result=release.helpers.compose(release.NEW,'exec','-T','backend','python','-c',backup,log=False,timeout=3600)
        verified=json.loads(result.strip().splitlines()[-1])
        assert verified['verified_encrypted'] is True, 'Backup verification failed'
        progress('installing_packages',backup=verified)
        apt('install',timeout=1800)
    release.preflight(release.TARGET)
    result=json.loads(STATE.read_text())
    result.update(status='success',phase='host_complete',updated=len(pins),
        reboot_performed=False,reboot_marker=Path('/var/run/reboot-required').exists())
    release.helpers.atomic_json(STATE,result)


def start(mode):
    with (release.CONTROL/'host-admission.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        previous=json.loads(STATE.read_text()) if STATE.exists() else {}
        assert previous.get('status') not in {'running','success'}
        if mode=='apply':assert previous.get('status')=='prepared'
        release.helpers.atomic_json(STATE,{'status':'running','phase':'starting_'+mode})
        with (release.CONTROL/'host-runner.log').open('w') as log:
            os.chmod(log.name,0o600)
            process=subprocess.Popen([sys.executable,__file__,'--run-'+mode],cwd=release.ROOT,
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        print(json.dumps({'status':'started','pid':process.pid,'mode':mode}))


def plan_diagnostic():
    """Return only public package transitions, excluding repository URLs/logs."""
    path=release.CONTROL/'host-apt.log'
    if not path.exists():return {'apt_log_present':False}
    data=path.read_text(errors='replace')[-65536:]
    changes=[]
    for line in data.splitlines():
        match=re.match(r'^Inst ([a-z0-9][a-z0-9+.:~-]*) (?:\[([^\]]+)\] )?\((\S+)',line)
        if match:
            name,old,new=match.groups();changes.append({'name':name,'old':old,'new':new})
    return {'apt_log_present':True,'transitions':changes[:201],
        'error_categories':[label for marker,label in (
            ('Unable to locate package','package_unavailable'),('unmet dependencies','dependency_conflict'),
            ('Failed to fetch','download_failed'),('Permission denied','permission_denied'),
            ('held broken packages','held_or_conflicting_packages'),
            ('a password is required','sudo_password_required'),('not allowed to execute','sudo_command_denied'),
            ('not in the sudoers','sudo_not_allowed'),('Could not get lock','apt_lock_busy'),
            ('is not signed','unsigned_repository'),('Release file','repository_release_problem'),
            ('Post-Invoke','repository_hook_failed'),('is not available','package_candidate_unavailable'),
            ('not found','not_found'),('sudo:','sudo_failure')) if marker in data]}


def helper_status():
    result={}
    for label,path in (('helper',Path('/usr/local/libexec/papermind-security-20261012')),
            ('sudoers',Path('/etc/sudoers.d/papermind-security-20261012'))):
        value={}
        try:
            info=path.lstat();value.update(present=True,symlink=path.is_symlink(),uid=info.st_uid,gid=info.st_gid,mode=oct(info.st_mode&0o777))
            if label=='helper' and info.st_size<65536:value['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        except FileNotFoundError:value.update(present=False)
        except PermissionError:value.update(readable=False,error_type='PermissionError')
        result[label]=value
    return result


def restart_advice():
    path=release.CONTROL/'host-apt.log'
    if not path.exists():return {'reported_services':[],'assessment':'not_reported'}
    data=path.read_text(errors='replace')[-262144:]
    services=set()
    for line in data.splitlines():
        match=re.fullmatch(r'\s*(?:sudo\s+)?systemctl restart ((?:[A-Za-z0-9_.@-]+\.service\s*)+)',line)
        if match:services.update(match.group(1).split())
    return {'reported_services':sorted(services)[:100],
        'no_services_reported': 'No services need to be restarted' in data,
        'kernel_up_to_date_reported':'Running kernel seems to be up-to-date' in data,
        'scope':'Only bounded APT/needrestart messages; no service restart performed by this status action'}


def service_status():
    result={}
    for unit in ('ssh.service','dbus.service','udisks2.service','smbd.service','winbind.service'):
        output=subprocess.run(['systemctl','show',unit,'--property=LoadState',
            '--property=ActiveState','--property=MainPID','--property=ExecMainStartTimestampMonotonic'],
            text=True,capture_output=True,timeout=10)
        fields=dict(line.split('=',1) for line in output.stdout.splitlines() if '=' in line)
        result[unit]={key:value for key,value in fields.items() if key in
            {'LoadState','ActiveState','MainPID','ExecMainStartTimestampMonotonic'}}
    return result


def library_activation():
    """Fixed library names and reload-event counts, without logs or addresses."""
    result={}
    units=service_status()
    for unit in ('ssh.service','dbus.service'):
        pid=units[unit].get('MainPID','0')
        if not pid.isdigit() or pid=='0':continue
        try:
            data=(Path('/proc')/pid/'maps').read_text()[:2*1024*1024]
            result[unit]={'maps_readable':True,'deleted_security_libraries':sorted({
                name for name in ('libcrypto.so.3','libssl.so.3','libexpat.so.1')
                if any(name in line and '(deleted)' in line for line in data.splitlines())})}
        except PermissionError:result[unit]={'maps_readable':False}
    protected={unit:units[unit]['MainPID'] for unit in ('ssh.service','dbus.service')
        if result.get(unit,{}).get('maps_readable') is False}
    if protected:
        assert all(pid.isdigit() and int(pid)>1 for pid in protected.values())
        program="import json;from pathlib import Path;targets="+repr(protected)+";result={}\nfor unit,pid in targets.items():\n try:\n  data=(Path('/proc')/pid/'maps').read_text()[:2*1024*1024];result[unit]={'maps_readable':True,'deleted_security_libraries':sorted({name for name in ('libcrypto.so.3','libssl.so.3','libexpat.so.1') if any(name in line and '(deleted)' in line for line in data.splitlines())})}\n except PermissionError:result[unit]={'maps_readable':False}\nprint(json.dumps(result))"
        image=json.loads(release.NEW.read_text())['services']['backend']['image']
        output=release.helpers.command(['docker','run','--rm','--network','none','--pid','host',
            '--read-only','--user','0:0','--cap-drop','ALL','--cap-add','SYS_PTRACE',
            '--security-opt','no-new-privileges','--memory','64m','--cpus','0.1',
            '--entrypoint','python',image,'-c',program],log=False,timeout=30)
        result.update(json.loads(output.strip().splitlines()[-1]))
    state=json.loads(STATE.read_text())
    if state.get('backup',{}).get('backup_id'):
        import uuid
        identifier=str(uuid.UUID(state['backup']['backup_id']))
        code="from app.db.session import SessionLocal;from sqlalchemy import text;\nwith SessionLocal() as db:\n print(db.scalar(text('SELECT finished_at FROM backup_runs WHERE id=:identifier'),{'identifier':"+repr(identifier)+"}).isoformat())"
        since=release.helpers.compose(release.NEW,'exec','-T','backend','python','-c',code,log=False,timeout=20).strip().splitlines()[-1]
        journal=subprocess.run(['journalctl','--unit=ssh.service','--since='+since,
            '--lines=200','--no-pager','--output=json'],text=True,capture_output=True,timeout=15)
        messages=[]
        for line in journal.stdout.splitlines():
            try:messages.append(json.loads(line).get('MESSAGE',''))
            except ValueError:pass
        result['ssh_reload_events_after_backup']=sum('Received SIGHUP; restarting.' in m for m in messages)
        result['journal_readable']=journal.returncode==0 and 'not seeing messages' not in journal.stderr
    return result


def main():
    if sys.argv[1:]==['--plan']:start('plan')
    elif sys.argv[1:]==['--apply']:start('apply')
    elif sys.argv[1:]==['--run-plan']:plan()
    elif sys.argv[1:]==['--run-apply']:apply()
    elif sys.argv[1:]==['--status']:
        print(STATE.read_text() if STATE.exists() else '{"status":"not_started"}')
        if STATE.exists() and json.loads(STATE.read_text()).get('phase')=='backup':release.backup_progress(installed=True)
        print(json.dumps({'root_helper':helper_status()}))
        print(json.dumps({'host_services':service_status()}))
        if STATE.exists() and json.loads(STATE.read_text()).get('status')=='success':
            print(json.dumps({'restart_advice':restart_advice()}))
            print(json.dumps({'library_activation':library_activation()}))
            import pi_security_restart
            print(json.dumps({'restart_readiness':pi_security_restart.readiness()}))
            print(json.dumps({'restart_result':pi_security_restart.result()}))
        if PLAN.exists():print(PLAN.read_text())
        elif STATE.exists() and json.loads(STATE.read_text()).get('status')=='failed':print(json.dumps({'diagnostic':plan_diagnostic()}))
    else:raise ValueError('Unsupported fixed host operation')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        if sys.argv[1:] in (['--run-plan'],['--run-apply']):
            reasons={'Package removal is forbidden','Unrecognized package plan','New packages require separate review',
                'Unexpected system transition','Package plan bound','Fixed APT operation failed',
                'Audited package selection changed','Release staging phase differs','Host package state changed','APT plan changed'}
            release.helpers.atomic_json(STATE,{'status':'failed','error_type':type(exc).__name__,
                'error_reason':str(exc) if str(exc) in reasons else 'fixed_precondition_failed'})
        print(type(exc).__name__);raise SystemExit(1)
