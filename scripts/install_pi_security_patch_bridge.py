#!/usr/bin/env python3
"""Install only the fixed operations for the explicitly requested release."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import zlib

BRIDGE=Path('/Users/admin/Library/Application Support/PaperMind/papermind-pi-bridge.py')
PAYLOAD=BRIDGE.with_name('papermind-security-release-20261012.json')
EXPECTED_FILES={'pi_security_patch.py': '1af44e775cdb99108b47eceb632e6173c0c93a7a9db767f8fefb9bc5e9c85e9a', 'pi_rollout.py': 'a59adea3a209bfbccb2da8bc35f3e748f76b5d961129b5608082f9645464449a', 'pi_audit.py': 'e534da063755d48d95cf4235ef2a253a25e4c9c665f0ccfc586026d84a77254b', 'pi_performance_probe.py': 'dd1dd42fb885ea35c3d95807cd4ae422e497de84a870eddc9b4f0a9f46d008af', 'audit_pi_packages.py': 'fa4cf15a7cad5e45636a98fb06e24f5087e6a88cf0de84d56f9b6bf810b934f8', 'pi_rollout_verify.py': '5d8173a1bc35b2a7981d1d5bbd8c95978ae5090718d846a7362d83a7925b612b', 'pi_security_verify.py': '935601e6c9253e47d52d0eaa7f87341384531a44e2dfb4947111f4347850a683', 'pi_host_security_patch.py': 'c884c2ca33d4b929d4bc3e5a818dc49bf7d03a2fa02c7e937bba660045b3b841', 'pi_host_security_packages.json': '1f33c8e41b124cfcefde637715e8793b0d48b2006a7f6b4198e432186a75c9e4', 'pi_host_security_root.py': '729b298d38d1bc68a4a6e67ee9956e17cf9f140abb9c890e99475845e88727c8', 'pi_host_security_sudoers': '8a8bea916720773ba1a1923f512aafcdfbe3d0a9aa8879e32d69a0c7bd2a53b1', 'pi_security_restart.py': '63759fa1ab7b2e1073e441202b41c641b3ed7ea547fc1f7d09e4e3b3d700e7f0'}
ARCHIVE_SHA256='1fd05022e17d55df664de78c80c2e0c9a61aa32f0c2ab7d4751f53450176ec30'


def main():
    directory=Path(__file__).parent
    values={}
    for name,expected in EXPECTED_FILES.items():
        data=(directory/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==expected, 'Fixed runner checksum mismatch'
        values[name]=data.decode()
    assert len(values)==12
    payload=Path('/Users/admin/Documents/paperMind/.runtime/security-patch/release-payload.json').read_text()
    release=json.loads(payload)
    assert release['archive_sha256']==ARCHIVE_SHA256
    assert hashlib.sha256(base64.b64decode(release['archive_base64'],validate=True)).hexdigest()==ARCHIVE_SHA256
    packed=base64.b64encode(zlib.compress(json.dumps(values).encode(),9)).decode()
    operations={
        'security_patch_prepare':('pi_security_patch.py','--prepare',180),
        'security_patch_rollout':('pi_security_patch.py','--apply',180),
        'security_patch_status':('pi_security_patch.py','--status',180),
        'security_patch_inventory':('pi_security_patch.py','--inventory',600),
        'security_patch_verify':('pi_security_verify.py','--runtime',180),
        'security_patch_measure':('pi_security_verify.py','--measure',180),
        'security_patch_measure_status':('pi_security_verify.py','--status',180),
        'security_patch_live_inventory':('pi_security_verify.py','--inventory',210),
        'security_patch_host_plan':('pi_host_security_patch.py','--plan',180),
        'security_patch_host_apply':('pi_host_security_patch.py','--apply',180),
        'security_patch_host_status':('pi_host_security_patch.py','--status',180),
        'security_patch_restart':('pi_security_restart.py','--request',90),
    }
    commands={}
    for action,(script,mode,timeout) in operations.items():
        program='import base64,hashlib,json,runpy,sys,zlib;from pathlib import Path;'
        program+="p=Path('/home/jan/papermind/.runtime/pi-security-patch');assert not p.is_symlink() and not p.parent.is_symlink();p.mkdir(parents=True,exist_ok=True);p.chmod(0o700);"
        program+=f'files=json.loads(zlib.decompress(base64.b64decode({packed!r})));expected={EXPECTED_FILES!r};assert set(files)==set(expected);'
        program+="assert all(not (p/n).is_symlink() for n in files);[(lambda n,d:(hashlib.sha256(d).hexdigest()==expected[n] or sys.exit(1),(p/n).write_bytes(d),(p/n).chmod(0o700)))(n,t.encode()) for n,t in files.items()];"
        program+=f'sys.path.insert(0,str(p));s=p/{script!r};sys.argv=[str(s),{mode!r}];runpy.run_path(str(s),run_name="__main__")'
        command='python3 -c '+shlex.quote(program)
        assert len(command.encode())<100000, 'Fixed command size bound'
        commands[action]=(command,timeout)
    begin='# BEGIN fixed October 12 security release\n';end='# END fixed October 12 security release\n'
    text=BRIDGE.read_text()
    if begin in text:
        prefix,tail=text.split(begin,1);_,suffix=tail.split(end,1);text=prefix+suffix
    addition=begin+'ACTIONS.update('+repr(commands)+')\n'
    addition+='ACTION_INPUT_PATHS.update({"security_patch_prepare":Path('+repr(str(PAYLOAD))+')})\n'+end
    addition=addition.replace(end,'ACTIONS["status"]=("cd /home/jan/papermind && git rev-parse --short HEAD && docker compose --env-file .env.prod -f docker-compose.prod.yml ps --format \'{{.Service}} {{.Status}}\'; if test -f .runtime/pi-security-patch/installed.json; then cat .runtime/pi-security-patch/installed.json; elif test -f .runtime/pi-rollout/installed.json; then cat .runtime/pi-rollout/installed.json; fi",60)\n'+end)
    anchor='\ndef configure_logging()';assert text.count(anchor)==1
    updated=text.replace(anchor,'\n'+addition+anchor);compile(updated,str(BRIDGE),'exec')
    backup=BRIDGE.with_suffix('.before-security-release.bak')
    if not backup.exists():shutil.copy2(BRIDGE,backup)
    PAYLOAD.write_text(payload);PAYLOAD.chmod(0o600)
    pending=BRIDGE.with_suffix('.security-release.part');pending.write_text(updated)
    pending.chmod(BRIDGE.stat().st_mode&0o777);pending.replace(BRIDGE)
    print(json.dumps({'fixed_actions':list(commands),'archive_sha256':ARCHIVE_SHA256,'payload_bytes':len(payload)}))


if __name__=='__main__':main()
