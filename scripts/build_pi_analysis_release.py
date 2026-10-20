#!/usr/bin/env python3
"""Build the reproducible October 20 analysis release payload from the fixed commit."""
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
TARGET = '2455897b679244f28a0f81a67022be95e4f52fa0'
EXCLUDED = 'deploy/host-control/'
OUTPUT = ROOT / '.runtime/analysis-release-20261020'


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def build():
    rows = git('ls-tree', '-r', '-z', TARGET).split(b'\0')
    raw = io.BytesIO()
    files = 0
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.PAX_FORMAT) as tar:
        for row in filter(None, rows):
            meta, name = row.split(b'\t', 1)
            mode, kind, obj = meta.decode().split()
            name = name.decode()
            if name.startswith(EXCLUDED): continue
            assert kind == 'blob' and mode in {'100644', '100755'}, 'Unsupported tree entry: ' + name
            data = git('cat-file', 'blob', obj)
            member = tarfile.TarInfo(name)
            member.size, member.mode, member.mtime = len(data), 0o755 if mode == '100755' else 0o644, 0
            tar.addfile(member, io.BytesIO(data))
            files += 1
    archive = gzip.compress(raw.getvalue(), compresslevel=9, mtime=0)
    return archive, files


def main():
    archive, files = build()
    digest = hashlib.sha256(archive).hexdigest()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'release.tar.gz').write_bytes(archive)
    payload = OUTPUT / 'release-payload.json'
    payload.write_text(json.dumps({'archive_base64': base64.b64encode(archive).decode(), 'archive_sha256': digest}))
    payload.chmod(0o600)
    print(json.dumps({'target': TARGET, 'archive_sha256': digest, 'archive_bytes': len(archive), 'files': files}))


if __name__ == '__main__': main()
