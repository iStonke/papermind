#!/usr/bin/env python3
"""Install only the immutable October 19 import release in the local Pi bridge."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import sys
import zlib

ROOT = Path('/Users/admin/Documents/paperMind')
BRIDGE = Path('/Users/admin/Library/Application Support/PaperMind/papermind-pi-bridge.py')
PAYLOAD = BRIDGE.with_name('papermind-import-release-20261019.json')
MANIFEST = ROOT / 'deploy/import-release-2026-10-19.json'
MANIFEST_SHA256 = '03f88f2ef9c8d56c2e838b6e203a5b0daf525b10f04d296522e3a89f63a9eef2'


def fixed_commands(manifest, values):
    assert manifest['base'] == '575d9b375f9ebde219f72df8bb7f5a86df72e529'
    assert manifest['target'] == '8d87348e079477d304a61523e5a7187155187f2b'
    assert manifest['archive_sha256'] == '93ae3ca356f66b9c7beb11396160ac511b15a1be37bb0a7ca2bc5c74d9108f7c'
    expected = manifest['runners']
    assert set(expected) == set(values) == {'pi_import_release.py', 'pi_rollout.py'}
    assert all(hashlib.sha256(value.encode()).hexdigest() == expected[name] for name, value in values.items())
    packed = base64.b64encode(zlib.compress(json.dumps(values).encode(), 9)).decode()
    commands = {}
    for action, mode in {'inspect': '--inspect', 'prepare': '--prepare', 'apply': '--apply', 'status': '--status', 'verify': '--verify'}.items():
        program = 'import base64,hashlib,json,runpy,sys,zlib;from pathlib import Path;sys.dont_write_bytecode=True;'
        program += "p=Path('/home/jan/papermind/.runtime/import-release-20261019');assert not p.is_symlink() and not p.parent.is_symlink();p.mkdir(parents=True,exist_ok=True,mode=0o700);p.chmod(0o700);"
        program += f'files=json.loads(zlib.decompress(base64.b64decode({packed!r})));expected={expected!r};assert set(files)==set(expected);'
        program += "assert all(not (p/n).is_symlink() for n in files);"
        program += "assert all(hashlib.sha256(t.encode()).hexdigest()==expected[n] for n,t in files.items());"
        program += "assert all(not (p/n).exists() or hashlib.sha256((p/n).read_bytes()).hexdigest()==expected[n] for n in files);"
        program += "[(p/n).write_text(t) for n,t in files.items() if not (p/n).exists()];[(p/n).chmod(0o700) for n in files];"
        program += f"sys.path.insert(0,str(p));s=p/'pi_import_release.py';sys.argv=[str(s),{mode!r}];runpy.run_path(str(s),run_name='__main__')"
        command = 'python3 -c ' + shlex.quote(program)
        assert len(command.encode()) < 100000
        commands['import_release_' + action] = (command, 180)
    return commands


def main():
    assert len(sys.argv) == 1, 'No free parameters are accepted'
    raw_manifest = MANIFEST.read_bytes()
    assert hashlib.sha256(raw_manifest).hexdigest() == MANIFEST_SHA256, 'Fixed manifest changed'
    manifest = json.loads(raw_manifest)
    values = {name: (ROOT / 'scripts' / name).read_text() for name in manifest['runners']}
    commands = fixed_commands(manifest, values)
    payload = (ROOT / '.runtime/import-release-20261019/release-payload.json').read_bytes()
    parsed = json.loads(payload)
    assert set(parsed) == {'archive_base64', 'archive_sha256'}
    assert parsed['archive_sha256'] == manifest['archive_sha256']
    assert hashlib.sha256(base64.b64decode(parsed['archive_base64'], validate=True)).hexdigest() == manifest['archive_sha256']
    assert not BRIDGE.is_symlink() and not PAYLOAD.is_symlink()
    text = BRIDGE.read_text()
    begin, end = '# BEGIN fixed October 19 import release\n', '# END fixed October 19 import release\n'
    if begin in text:
        prefix, tail = text.split(begin, 1)
        _, suffix = tail.split(end, 1)
        text = prefix + suffix
    anchor = '\ndef configure_logging()'
    assert text.count(anchor) == 1 and 'ACTION_INPUT_PATHS' in text
    addition = begin + 'ACTIONS.update(' + repr(commands) + ')\n'
    addition += 'ACTION_INPUT_PATHS.update({"import_release_prepare":Path(' + repr(str(PAYLOAD)) + ')})\n'
    status = "cd /home/jan/papermind && git rev-parse --short HEAD && docker compose --env-file .env.prod -f docker-compose.prod.yml ps --format '{{.Service}} {{.Status}}'; if test -f .runtime/import-release-20261019/installed.json; then cat .runtime/import-release-20261019/installed.json; elif test -f .runtime/pi-security-patch/installed.json; then cat .runtime/pi-security-patch/installed.json; fi"
    addition += 'ACTIONS["status"]=' + repr((status, 60)) + '\n' + end
    prefix, suffix = text.split(anchor)
    updated = prefix.rstrip('\n') + '\n\n' + addition + '\ndef configure_logging()' + suffix
    compile(updated, str(BRIDGE), 'exec')
    backup = BRIDGE.with_suffix('.before-import-release-20261019.bak')
    if not backup.exists(): shutil.copy2(BRIDGE, backup)
    pending_payload = PAYLOAD.with_suffix('.part')
    assert not pending_payload.is_symlink()
    with pending_payload.open('wb') as handle:
        pending_payload.chmod(0o600)
        handle.write(payload)
    pending_payload.replace(PAYLOAD)
    pending = BRIDGE.with_suffix('.import-release.part')
    assert not pending.is_symlink()
    pending.write_text(updated)
    pending.chmod(BRIDGE.stat().st_mode & 0o777)
    pending.replace(BRIDGE)
    print(json.dumps({'actions': list(commands), 'target': manifest['target'], 'archive_sha256': manifest['archive_sha256']}))


if __name__ == '__main__': main()
