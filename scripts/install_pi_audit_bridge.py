#!/usr/bin/env python3
"""Install only the three explicitly approved, checksum-pinned audit actions."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import shutil

BRIDGE = Path('/Users/admin/Library/Application Support/PaperMind/papermind-pi-bridge.py')
REMOTE = '/home/jan/papermind/.runtime/pi-audit-2026-10-12-code'
RUNNER_SHA256 = 'f57b069276bb2cb9127366455f009df48766da152744e6af6f0fdf132175a069'
PROBE_SHA256 = 'dd1dd42fb885ea35c3d95807cd4ae422e497de84a870eddc9b4f0a9f46d008af'


def main():
    source = Path(__file__).parent
    files = {'pi_audit.py': ((source / 'pi_audit.py').read_bytes(), RUNNER_SHA256),
        'pi_performance_probe.py': ((source / 'pi_performance_probe.py').read_bytes(), PROBE_SHA256)}
    for data, expected in files.values():
        assert hashlib.sha256(data).hexdigest() == expected, 'Audit code checksum mismatch'
    commands = {}
    for action, mode in (('performance_audit', '--start'), ('performance_audit_status', '--status'), ('security_inventory', '--inventory')):
        program = 'import base64,hashlib,runpy,sys;from pathlib import Path;'
        program += f'p=Path({REMOTE!r});p.mkdir(parents=True,exist_ok=True);p.chmod(0o700);'
        for name, (data, expected) in files.items():
            program += f'd=base64.b64decode({base64.b64encode(data).decode()!r});'
            program += f'assert hashlib.sha256(d).hexdigest()=={expected!r};'
            program += f'f=p/{name!r};f.write_bytes(d);f.chmod(0o700);'
        program += f's=p/"pi_audit.py";sys.argv=[str(s),{mode!r}];runpy.run_path(str(s),run_name="__main__")'
        commands[action] = ('python3 -c ' + shlex.quote(program), 180)
    begin = '# BEGIN fixed PaperMind October 12 audit\n'
    end = '# END fixed PaperMind October 12 audit\n'
    text = BRIDGE.read_text()
    if begin in text:
        prefix, tail = text.split(begin, 1)
        _, suffix = tail.split(end, 1)
        text = prefix + suffix
    anchor = '\ndef configure_logging()'
    assert text.count(anchor) == 1, 'Unexpected bridge structure'
    updated = text.replace(anchor, '\n' + begin + 'ACTIONS.update(' + repr(commands) + ')\n' + end + anchor)
    compile(updated, str(BRIDGE), 'exec')
    backup = BRIDGE.with_suffix('.py.before-audit-2026-10-12.bak')
    if not backup.exists():
        shutil.copy2(BRIDGE, backup)
    pending = BRIDGE.with_suffix('.py.audit.part')
    pending.write_text(updated)
    pending.chmod(BRIDGE.stat().st_mode & 0o777)
    pending.replace(BRIDGE)
    print(json.dumps({'actions': list(commands), 'runner_sha256': RUNNER_SHA256, 'probe_sha256': PROBE_SHA256}))


if __name__ == '__main__':
    main()
