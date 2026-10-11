#!/usr/bin/env python3
"""Adopt one approved rollout in Git without deploying or discarding local work.

The bridge runs this fixed program; it accepts no host, ref, path or command.
The adjacent manifest is checksum-pinned and contains only public source hashes.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path('/home/jan/papermind')
SPEC_SHA256 = '247e613777558b951013f566eb8ddfe2f40301ce5ef711a42cb36a9b4bad887c'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    parts = PurePosixPath(name).parts
    return bool(parts and not name.startswith('/') and '..' not in parts
        and not any(part in {'.git', '.runtime', 'node_modules', '__pycache__', 'dist'} for part in parts)
        and not any(part.startswith('.env') and part not in {'.env.example', '.env.prod.example'} for part in parts))


class Reconcile:
    def __init__(self, root, spec):
        self.root = Path(root)
        self.spec = spec
        self.branch = 'refs/heads/' + spec['branch']
        assert all(safe_name(name) for name in spec['files']), 'Unsafe manifest path'

    def git(self, *args, check=True):
        result = subprocess.run(['git', *args], cwd=self.root, capture_output=True, timeout=120)
        if check and result.returncode:
            raise RuntimeError(f'Git {args[0]} failed with exit {result.returncode}')
        return result

    def value(self, *args):
        return self.git(*args).stdout.decode().strip()

    def path(self, name):
        path = self.root / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if self.root in parent.parents or parent == self.root):
            raise ValueError('Symlink in source path: ' + name)
        if path.exists() and not path.is_file():
            raise ValueError('Source is not a regular file: ' + name)
        return path

    def inspect(self):
        installed = json.loads((self.root / '.runtime/pi-rollout/installed.json').read_text())
        assert installed['archive_sha256'] == self.spec['rollout_sha256'], 'Unexpected installed rollout'
        head = self.value('rev-parse', 'HEAD')
        assert head in {self.spec['base'], self.spec['target']}, 'Unexpected Git HEAD'
        assert self.value('symbolic-ref', 'HEAD') == self.branch, 'Unexpected Git branch'
        assert self.git('diff', '--cached', '--quiet', check=False).returncode == 0, 'Existing staged changes'
        changed = self.value('diff', '--name-only', 'HEAD').splitlines()
        unknown = sorted(set(changed) - self.spec['files'].keys())
        assert not unknown, 'Unapproved tracked changes: ' + ', '.join(unknown)
        for name, entry in self.spec['files'].items():
            path = self.path(name)
            current = digest(path.read_bytes()) if path.exists() else None
            allowed = {value for value in (entry['base_sha256'], entry['rollout_sha256'], entry['target_sha256']) if value is not None}
            if entry['base_sha256'] is None:
                allowed.add(None)
            assert current in allowed, 'Unapproved source content: ' + name
        return {'head': head, 'target': self.spec['target'], 'tracked_changes': changed,
                'files': len(self.spec['files'])}

    def apply(self, *, fetch=True):
        initial = self.inspect()
        control = self.root / '.runtime/pi-git-reconcile'
        control.mkdir(mode=0o700, parents=True, exist_ok=True)
        control.chmod(0o700)
        with (control / 'operation.lock').open('a+') as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if fetch:
                self.git('fetch', 'origin', self.spec['branch'])
                self.git('merge-base', '--is-ancestor', self.spec['target'], 'FETCH_HEAD')
            self.git('merge-base', '--is-ancestor', self.spec['base'], self.spec['target'])
            self.inspect()
            target_content = {}
            for name, entry in self.spec['files'].items():
                data = self.git('show', self.spec['target'] + ':' + name).stdout
                assert digest(data) == entry['target_sha256'], 'Target checksum mismatch: ' + name
                target_content[name] = data
            if initial['head'] == self.spec['target']:
                assert not initial['tracked_changes'], 'Target checkout still has modifications'
                return {**initial, 'status': 'already_reconciled'}

            run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
            backup = control / (run_id + '-' + self.spec['target'][:12])
            backup.mkdir(mode=0o700)
            original = {}
            for name in self.spec['files']:
                path = self.path(name)
                data = path.read_bytes() if path.exists() else None
                mode = stat.S_IMODE(path.stat().st_mode) if data is not None else None
                original[name] = (data, mode)
                if data is not None:
                    saved = backup / 'source' / name
                    saved.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    saved.write_bytes(data)
                    saved.chmod(0o600)
            manifest = {'base': initial['head'], 'target': self.spec['target'],
                'files': {name: {'sha256': digest(data) if data is not None else None, 'mode': mode}
                          for name, (data, mode) in original.items()}}
            (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
            (backup / 'manifest.json').chmod(0o600)
            written = []
            ref_changed = False
            try:
                assert self.value('rev-parse', 'HEAD') == self.spec['base'], 'Git changed during backup'
                for name, entry in self.spec['files'].items():
                    path = self.path(name)
                    data, mode = original[name]
                    assert (path.read_bytes() if path.exists() else None) == data, 'Source changed during backup: ' + name
                    if data != target_content[name] or mode != entry['mode']:
                        written.append(name)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        # Preserve inodes, including the Caddy single-file bind mount.
                        path.write_bytes(target_content[name])
                        path.chmod(entry['mode'])
                self.git('update-ref', '-m', 'PaperMind: adopt verified rollout in Git', self.branch,
                         self.spec['target'], self.spec['base'])
                ref_changed = True
                self.git('read-tree', self.spec['target'])
                assert self.git('diff', '--quiet', check=False).returncode == 0, 'Tracked source differs after reconciliation'
                assert self.git('diff', '--cached', '--quiet', check=False).returncode == 0, 'Index differs after reconciliation'
            except Exception:
                if ref_changed:
                    self.git('update-ref', self.branch, self.spec['base'], self.spec['target'])
                    self.git('read-tree', self.spec['base'])
                for name in reversed(written):
                    path = self.path(name)
                    data, mode = original[name]
                    # A concurrent edit must survive rather than being overwritten.
                    assert not path.exists() or digest(path.read_bytes()) == self.spec['files'][name]['target_sha256'], 'Concurrent edit needs manual recovery: ' + name
                    if data is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_bytes(data)
                        path.chmod(mode)
                raise
            return {'status': 'success', 'head': self.spec['target'], 'backup': str(backup),
                    'tracked_changes': [], 'source_files_updated': len(written)}


def main():
    args = sys.argv[1:]
    assert args in [[], ['--inspect'], ['--apply']], 'Unsupported fixed operation'
    raw = Path(__file__).with_suffix('.json').read_bytes()
    assert digest(raw) == SPEC_SHA256, 'Manifest checksum mismatch'
    reconcile = Reconcile(ROOT, json.loads(raw))
    result = reconcile.apply() if args == ['--apply'] else reconcile.inspect()
    print(json.dumps(result))


if __name__ == '__main__':
    main()
