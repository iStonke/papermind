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
    apt('update')
    packages=parse_plan(apt('plan'))
    pins=[p['name']+'='+p['new'] for p in packages]
    if pins:apt('download')
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
        simulated=parse_plan(apt('verify'))
        assert sorted(simulated,key=lambda p:p['name'])==sorted(value['packages'],key=lambda p:p['name']), 'APT plan changed'
        # Preserve a second encrypted recovery copy without replacing rollout backup.
        backup=release.BACKUP.replace('security-patch-backup-20261012','security-host-backup-20261012')
        release.helpers.compose(release.NEW,'exec','-T','backend','python','-c',backup,log=False,timeout=3600)
        apt('install',timeout=1800)
    release.preflight(release.TARGET)
    release.helpers.atomic_json(STATE,{'status':'success','phase':'host_complete','updated':len(pins),
        'reboot_performed':False,'reboot_marker':Path('/var/run/reboot-required').exists()})


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


def main():
    if sys.argv[1:]==['--plan']:start('plan')
    elif sys.argv[1:]==['--apply']:start('apply')
    elif sys.argv[1:]==['--run-plan']:plan()
    elif sys.argv[1:]==['--run-apply']:apply()
    elif sys.argv[1:]==['--status']:
        print(STATE.read_text() if STATE.exists() else '{"status":"not_started"}')
        print(json.dumps({'root_helper':helper_status()}))
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
