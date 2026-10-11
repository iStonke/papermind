#!/usr/bin/env python3
"""Install the explicitly approved fixed Git reconciliation in the local bridge.

Keeps the existing socket, SSH arguments and all existing actions unchanged.
Run locally on this Mac; the two operations accept no request parameters.
"""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import shutil

BRIDGE = Path('/Users/admin/Library/Application Support/PaperMind/papermind-pi-bridge.py')
RUNNER_SHA256 = '686372ef84b2b8684ebfa88ba948f11b7d87e9f8ed453436d44aa3ff91586d7f'
MANIFEST_SHA256 = '247e613777558b951013f566eb8ddfe2f40301ce5ef711a42cb36a9b4bad887c'
REMOTE = '/home/jan/papermind/.runtime/pi-git-reconcile-runner'


def main():
    source = Path(__file__).parent
    runner = (source / 'pi_git_reconcile.py').read_bytes()
    manifest = (source / 'pi_git_reconcile.json').read_bytes()
    assert hashlib.sha256(runner).hexdigest() == RUNNER_SHA256, 'Runner checksum mismatch'
    assert hashlib.sha256(manifest).hexdigest() == MANIFEST_SHA256, 'Manifest checksum mismatch'
    commands = {}
    for action, mode in (('git_reconcile_status', '--inspect'), ('git_reconcile', '--apply')):
        program = (
            'import base64,hashlib,runpy,sys;from pathlib import Path;'
            f'p=Path({REMOTE!r});p.mkdir(parents=True,exist_ok=True);p.chmod(0o700);'
            f'r=base64.b64decode({base64.b64encode(runner).decode()!r});'
            f'm=base64.b64decode({base64.b64encode(manifest).decode()!r});'
            f'assert hashlib.sha256(r).hexdigest()=={RUNNER_SHA256!r};'
            f'assert hashlib.sha256(m).hexdigest()=={MANIFEST_SHA256!r};'
            's=p/"pi_git_reconcile.py";s.write_bytes(r);s.chmod(0o700);'
            'j=p/"pi_git_reconcile.json";j.write_bytes(m);j.chmod(0o600);'
            f'sys.argv=[str(s),{mode!r}];runpy.run_path(str(s),run_name="__main__")'
        )
        commands[action] = ('python3 -c ' + shlex.quote(program), 180)
    start = '# BEGIN fixed PaperMind Git reconciliation\n'
    end = '# END fixed PaperMind Git reconciliation\n'
    text = BRIDGE.read_text()
    if start in text:
        prefix, tail = text.split(start, 1)
        _, suffix = tail.split(end, 1)
        text = prefix + suffix
    addition = start + 'ACTIONS.update(' + repr(commands) + ')\n' + end
    anchor = '\ndef configure_logging()'
    assert text.count(anchor) == 1, 'Unexpected bridge layout'
    updated = text.replace(anchor, '\n' + addition + anchor)
    compile(updated, str(BRIDGE), 'exec')
    backup = BRIDGE.with_suffix('.py.before-git-reconcile.bak')
    if not backup.exists():
        shutil.copy2(BRIDGE, backup)
    pending = BRIDGE.with_suffix('.py.git-reconcile.part')
    pending.write_text(updated)
    pending.chmod(BRIDGE.stat().st_mode & 0o777)
    pending.replace(BRIDGE)
    print(json.dumps({'installed_actions': list(commands), 'target': json.loads(manifest)['target'],
        'runner_sha256': RUNNER_SHA256, 'previous_bridge_backup': str(backup)}))


if __name__ == '__main__':
    main()
