#!/usr/bin/env python3
"""Install the fixed inspection supporting the requested patch rollout."""
import base64
import hashlib
from pathlib import Path
import shlex
import shutil

BRIDGE = Path('/Users/admin/Library/Application Support/PaperMind/papermind-pi-bridge.py')
EXPECTED_SHA256 = '7c190c3f5881f2f9887b2de9ed36e97ea27baeaf1bb0cc0094ea64b6f7c790f2'


def main():
    data = Path(__file__).with_name('pi_patch_inspect.py').read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED_SHA256
    program = 'import base64,hashlib,runpy;from pathlib import Path;'
    program += "p=Path('/home/jan/papermind/.runtime/pi-security-patch/inspect.py');p.parent.mkdir(parents=True,exist_ok=True);p.parent.chmod(0o700);"
    program += f'd=base64.b64decode({base64.b64encode(data).decode()!r});assert hashlib.sha256(d).hexdigest()=={EXPECTED_SHA256!r};'
    program += 'p.write_bytes(d);p.chmod(0o700);runpy.run_path(str(p),run_name="__main__")'
    addition = '# BEGIN fixed security patch inspection\nACTIONS.update(' + repr({'security_patch_inspect': ('python3 -c ' + shlex.quote(program), 210)}) + ')\n# END fixed security patch inspection\n'
    text = BRIDGE.read_text()
    assert '# BEGIN fixed security patch inspection' not in text
    anchor = '\ndef configure_logging()'
    assert text.count(anchor) == 1
    updated = text.replace(anchor, '\n' + addition + anchor)
    compile(updated, str(BRIDGE), 'exec')
    backup = BRIDGE.with_suffix('.before-security-inspect.bak')
    if not backup.exists():
        shutil.copy2(BRIDGE, backup)
    pending = BRIDGE.with_suffix('.security-inspect.part')
    pending.write_text(updated)
    pending.chmod(BRIDGE.stat().st_mode & 0o777)
    pending.replace(BRIDGE)
    print('Fixed security_patch_inspect installed')


if __name__ == '__main__':
    main()
