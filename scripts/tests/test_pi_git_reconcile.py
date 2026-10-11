import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

module_spec = importlib.util.spec_from_file_location('pi_git_reconcile', Path(__file__).parents[1] / 'pi_git_reconcile.py')
module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(module)


class GitReconcileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-b', 'feat/ki-chat-integration')
        self.git('config', 'user.name', 'PaperMind test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'core.hooksPath', '/dev/null')
        self.put('.gitignore', b'.env\n.runtime/\nuser-data/\n')
        self.put('backend/a.py', b'print("base")\n')
        self.put('backend/unrelated.py', b'untouched\n')
        self.put('deploy/Caddyfile', b':80 { reverse_proxy frontend:80 }\n')
        self.git('add', '.')
        self.git('commit', '-m', 'base')
        self.base = self.git('rev-parse', 'HEAD').decode().strip()
        self.target_files = {
            'backend/a.py': b'print("optimized")\n',
            'frontend/live.js': b'export const liveReview = true;\n',
            'deploy/Caddyfile': b':80 { encode gzip; reverse_proxy frontend:80 }\n',
        }
        for name, data in self.target_files.items():
            self.put(name, data)
        self.git('add', '.')
        self.git('commit', '-m', 'target includes live review')
        self.target = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('reset', '--hard', self.base)  # Disposable fixture only.
        self.rollout_files = {**self.target_files, 'backend/a.py': b'print("optimized")\n\n'}
        for name, data in self.rollout_files.items():
            self.put(name, data)
        self.put('.env', b'PRIVATE_LOCAL_SETTING=preserve-me\n')
        self.put('user-data/document.pdf', b'private user document fixture')
        self.put('.runtime/pi-rollout/installed.json', json.dumps({'archive_sha256': 'approved-rollout'}).encode())
        entries = {}
        for name, data in self.target_files.items():
            base = subprocess.run(['git', 'show', self.base + ':' + name], cwd=self.root, capture_output=True)
            entries[name] = {'base_sha256': module.digest(base.stdout) if base.returncode == 0 else None,
                'rollout_sha256': module.digest(self.rollout_files[name]), 'target_sha256': module.digest(data), 'mode': 0o644}
        self.spec = {'base': self.base, 'target': self.target, 'branch': 'feat/ki-chat-integration',
            'rollout_sha256': 'approved-rollout', 'files': entries}
        self.runner = module.Reconcile(self.root, self.spec)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.DEVNULL)

    def put(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def assert_original_source(self):
        self.assertEqual(self.git('rev-parse', 'HEAD').decode().strip(), self.base)
        for name, data in self.rollout_files.items():
            self.assertEqual((self.root / name).read_bytes(), data)
        self.assertEqual(self.git('diff', '--cached', '--name-only'), b'')
        self.assertEqual((self.root / '.env').read_bytes(), b'PRIVATE_LOCAL_SETTING=preserve-me\n')

    def test_preserves_live_feature_user_data_and_caddy_inode_with_verified_backup(self):
        inode = (self.root / 'deploy/Caddyfile').stat().st_ino
        result = self.runner.apply(fetch=False)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.git('rev-parse', 'HEAD').decode().strip(), self.target)
        self.assertEqual(self.git('status', '--porcelain', '--untracked-files=no'), b'')
        self.assertEqual((self.root / 'deploy/Caddyfile').stat().st_ino, inode)
        self.assertEqual((self.root / 'frontend/live.js').read_bytes(), self.target_files['frontend/live.js'])
        self.assertEqual((self.root / 'user-data/document.pdf').read_bytes(), b'private user document fixture')
        self.assertEqual((self.root / '.env').read_bytes(), b'PRIVATE_LOCAL_SETTING=preserve-me\n')
        backup = Path(result['backup'])
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        manifest = json.loads((backup / 'manifest.json').read_text())
        for name, data in self.rollout_files.items():
            saved = backup / 'source' / name
            self.assertEqual(saved.read_bytes(), data)
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(), manifest['files'][name]['sha256'])
        self.assertEqual(self.runner.apply(fetch=False)['status'], 'already_reconciled')

    def test_unknown_tracked_edit_aborts_without_source_or_ref_changes(self):
        self.put('backend/unrelated.py', b'new independent work\n')
        with self.assertRaisesRegex(AssertionError, 'Unapproved tracked'):
            self.runner.apply(fetch=False)
        self.assert_original_source()
        self.assertEqual((self.root / 'backend/unrelated.py').read_bytes(), b'new independent work\n')

    def test_unknown_content_in_allowed_file_is_preserved(self):
        self.put('backend/a.py', b'concurrent independent work\n')
        with self.assertRaisesRegex(AssertionError, 'Unapproved source content'):
            self.runner.apply(fetch=False)
        self.assertEqual((self.root / 'backend/a.py').read_bytes(), b'concurrent independent work\n')
        self.assertEqual(self.git('rev-parse', 'HEAD').decode().strip(), self.base)

    def test_staged_work_aborts(self):
        self.git('add', 'backend/a.py')
        before = self.git('diff', '--cached', '--binary')
        with self.assertRaisesRegex(AssertionError, 'Existing staged'):
            self.runner.apply(fetch=False)
        self.assertEqual(self.git('diff', '--cached', '--binary'), before)

    def test_deleted_existing_file_is_not_silently_recreated(self):
        (self.root / 'backend/a.py').unlink()
        with self.assertRaisesRegex(AssertionError, 'Unapproved source content'):
            self.runner.apply(fetch=False)
        self.assertFalse((self.root / 'backend/a.py').exists())

    def test_symlink_does_not_overwrite_private_file(self):
        (self.root / 'frontend/live.js').unlink()
        (self.root / 'frontend/live.js').symlink_to(self.root / '.env')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.runner.apply(fetch=False)
        self.assertEqual((self.root / '.env').read_bytes(), b'PRIVATE_LOCAL_SETTING=preserve-me\n')

    def test_wrong_rollout_identity_aborts(self):
        self.put('.runtime/pi-rollout/installed.json', b'{"archive_sha256":"other"}')
        with self.assertRaisesRegex(AssertionError, 'Unexpected installed'):
            self.runner.apply(fetch=False)
        self.assert_original_source()

    def test_wrong_target_checksum_aborts_before_writes(self):
        self.spec['files']['backend/a.py']['target_sha256'] = '0' * 64
        with self.assertRaisesRegex(AssertionError, 'Target checksum'):
            self.runner.apply(fetch=False)
        self.assert_original_source()

    def test_failed_index_update_rolls_back_ref_and_source(self):
        real_git = self.runner.git
        def failing_git(*args, **kwargs):
            if args == ('read-tree', self.target):
                raise RuntimeError('synthetic index failure')
            return real_git(*args, **kwargs)
        with patch.object(self.runner, 'git', side_effect=failing_git):
            with self.assertRaisesRegex(RuntimeError, 'synthetic index failure'):
                self.runner.apply(fetch=False)
        self.assert_original_source()

    def test_secret_and_traversal_manifest_paths_are_rejected(self):
        for name in ('.env', '.runtime/secrets/key', '../outside', '/absolute', 'frontend/node_modules/x'):
            spec = {**self.spec, 'files': {name: self.spec['files']['backend/a.py']}}
            with self.assertRaisesRegex(AssertionError, 'Unsafe manifest'):
                module.Reconcile(self.root, spec)


if __name__ == '__main__':
    unittest.main()
