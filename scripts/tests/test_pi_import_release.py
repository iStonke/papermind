import base64
from contextlib import ExitStack
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shlex
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
import urllib.error
from unittest.mock import patch

SCRIPTS = Path(__file__).parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('import_release', SCRIPTS / 'pi_import_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ImportReleaseTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name, path in {'ROOT': root, 'CONTROL': root / 'control', 'STATE': root / 'control/state.json',
                           'SOURCE': root / 'source', 'OLD': root / 'control/old.json', 'NEW': root / 'control/new.json'}.items():
            mock = patch.object(release, name, path)
            mock.start()
            self.addCleanup(mock.stop)
        release.CONTROL.mkdir()
        self.before = {name: {'container': name, 'image': 'old-' + name} for name in release.ALL_SERVICES}
        self.old = {'services': {name: {'image': 'old-' + name} for name in release.ALL_SERVICES}}
        self.new = {'services': {name: {'image': 'new-' + name, 'build': {}, 'environment': {}} for name in release.ALL_SERVICES}}
        self.images = {name: 'id-' + name for name in release.SERVICES}
        release.OLD.write_text(json.dumps(self.old))
        release.NEW.write_text(json.dumps(self.new))
        release.STATE.write_text(json.dumps({'status': 'running', 'before': self.before, 'images': self.images}))
        self.events = []

    def compose(self, path, *args, **kwargs):
        self.events.append(('compose', path, *args))
        if release.BACKUP in args: return '{"verified_encrypted":true,"backup_id":"synthetic","bytes":100}'
        return ''

    def command(self, args, **kwargs):
        self.events.append(('command', *args))
        if args[:3] == ['docker', 'image', 'inspect']: return 'id-' + args[-1].removeprefix('new-')
        if args in (['git', 'rev-parse', 'HEAD'], ['git', 'rev-parse', release.TARGET]): return release.TARGET
        return ''

    def mocks(self):
        stack = ExitStack()
        stack.enter_context(patch.object(release, 'validate_source'))
        stack.enter_context(patch.object(release, 'preflight', return_value=self.before))
        stack.enter_context(patch.object(release.helpers, 'compose', side_effect=self.compose))
        stack.enter_context(patch.object(release.helpers, 'command', side_effect=self.command))
        stack.enter_context(patch.object(release.time, 'sleep'))
        return stack

    def test_modified_or_free_form_release_is_rejected(self):
        good = b'pinned archive'
        digest = hashlib.sha256(good).hexdigest()
        payload = {'archive_base64': base64.b64encode(good).decode(), 'archive_sha256': digest}
        with patch.object(release, 'ARCHIVE_SHA256', digest):
            self.assertEqual(release.validate_payload(json.dumps(payload)), good)
            for changed in [dict(payload, command='anything'), dict(payload, archive_base64='YWJj'), dict(payload, archive_sha256='other')]:
                with self.assertRaises(AssertionError): release.validate_payload(json.dumps(changed))

    def test_staged_source_tampering_is_rejected(self):
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w:gz') as tar:
            member = tarfile.TarInfo('file.txt')
            member.size = 3
            tar.addfile(member, io.BytesIO(b'new'))
        data = archive.getvalue()
        (release.CONTROL / 'release.tar.gz').write_bytes(data)
        release.SOURCE.mkdir()
        (release.SOURCE / 'file.txt').write_bytes(b'old')
        with patch.object(release, 'ARCHIVE_SHA256', hashlib.sha256(data).hexdigest()):
            with self.assertRaisesRegex(AssertionError, 'Staged source changed'): release.validate_source()

    def test_production_change_aborts_before_backup(self):
        with self.mocks(), patch.object(release, 'preflight', return_value={}):
            with self.assertRaisesRegex(AssertionError, 'Production changed'): release.apply()
        self.assertEqual(self.events, [])

    def test_retagged_candidate_aborts_before_backup(self):
        with self.mocks(), patch.object(release.helpers, 'command', return_value='unknown-image'):
            with self.assertRaisesRegex(AssertionError, 'Candidate image changed'): release.apply()
        self.assertFalse(any(row[0] == 'compose' for row in self.events))

    def test_backup_failure_never_stops_or_merges_production(self):
        original = self.compose
        def fail_backup(path, *args, **kwargs):
            if release.BACKUP in args: raise RuntimeError('synthetic backup failure')
            return original(path, *args, **kwargs)
        with self.mocks(), patch.object(release.helpers, 'compose', side_effect=fail_backup):
            with self.assertRaises(RuntimeError): release.apply()
        self.assertFalse(any('stop' in row or 'merge' in row or 'reset' in row for row in self.events))
        self.assertTrue(json.loads(release.STATE.read_text())['rollback_ok'])

    def test_success_orders_backup_drain_switch_migration_and_health(self):
        with self.mocks(): release.apply()
        backup = next(index for index, row in enumerate(self.events) if release.BACKUP in row)
        guard = next(index for index, row in enumerate(self.events) if release.GUARD in row)
        stop = next(index for index, row in enumerate(self.events) if 'stop' in row)
        merge = self.events.index(('command', 'git', 'merge', '--ff-only', release.TARGET))
        migrate = next(index for index, row in enumerate(self.events) if 'alembic' in row and 'upgrade' in row)
        health = next(index for index, row in enumerate(self.events) if release.VERIFY in row)
        self.assertEqual([backup, guard, stop, merge, migrate, health], sorted([backup, guard, stop, merge, migrate, health]))
        self.assertEqual(json.loads(release.STATE.read_text())['status'], 'success')
        self.assertFalse(any(row[0] == 'compose' and ('up' in row or 'stop' in row) and any(name in row for name in ('db', 'ai', 'caddy')) for row in self.events))
        self.assertIn(('command', 'docker', 'exec', release.GUARD_NAME, 'python', '-c', release.RELEASE), self.events)

    def test_migration_failure_restores_schema_git_and_images(self):
        original = self.compose
        def fail_upgrade(path, *args, **kwargs):
            if 'upgrade' in args: raise RuntimeError('synthetic migration failure')
            return original(path, *args, **kwargs)
        with self.mocks(), patch.object(release.helpers, 'compose', side_effect=fail_upgrade):
            with self.assertRaises(RuntimeError): release.apply()
        self.assertIn(('command', 'git', 'reset', '--hard', release.BASE), self.events)
        self.assertTrue(any('downgrade' in row and '113_drop_note_favorite' in row for row in self.events))
        self.assertTrue(json.loads(release.STATE.read_text())['rollback_ok'])
        for name in release.SERVICES: self.assertIn(('command', 'docker', 'tag', 'old-' + name, f'papermind-{name}:latest'), self.events)

    def test_build_failure_never_stops_production(self):
        with self.mocks(), patch.object(release.helpers, 'read_config', side_effect=[self.old, self.new]), \
             patch.object(release.helpers.shutil, 'disk_usage') as usage, \
             patch.object(release.helpers, 'compose', side_effect=RuntimeError('synthetic preflight/build failure')):
            usage.return_value.free = 20 * 1024**3
            with self.assertRaises(RuntimeError): release.prepare()
        self.assertFalse(any('stop' in row or 'merge' in row or 'reset' in row for row in self.events))

    def test_background_prepare_failure_is_reported_as_failed(self):
        with patch.object(sys, 'argv', ['runner', '--run-prepare']), patch.object(release, 'prepare', side_effect=RuntimeError('build failed')):
            with self.assertRaises(RuntimeError): release.main()
        state = json.loads(release.STATE.read_text())
        self.assertEqual(state['status'], 'failed')
        self.assertTrue(state['rollback_ok'])

    def test_free_cli_arguments_are_rejected(self):
        with patch.object(sys, 'argv', ['runner', '--apply', 'arbitrary-command']), patch.object(release, 'apply') as apply:
            with self.assertRaises(ValueError): release.main()
            apply.assert_not_called()

    def test_embedded_python_programs_compile(self):
        for name in ('IDLE', 'BACKUP', 'GUARD', 'READY', 'RELEASE', 'VERIFY', 'ACCESS_CHECK'):
            compile(getattr(release, name), name, 'exec')

    def test_anonymous_probe_respects_the_write_barrier_and_checks_auth_after_release(self):
        for maintenance, status in [(True, 503), (False, 401)]:
            with self.subTest(maintenance=maintenance), patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError('synthetic', status, '', None, None)):
                exec(release.ACCESS_CHECK, {'is_maintenance_active': lambda: maintenance})

    def test_anonymous_probe_never_accepts_public_access_or_a_wrong_status(self):
        for maintenance, status in [(True, 401), (False, 503), (False, 500)]:
            with self.subTest(maintenance=maintenance, status=status), patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError('synthetic', status, '', None, None)):
                with self.assertRaises(AssertionError): exec(release.ACCESS_CHECK, {'is_maintenance_active': lambda: maintenance})
        with patch('urllib.request.urlopen', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'Anonymous document access'): exec(release.ACCESS_CHECK, {'is_maintenance_active': lambda: False})


class ImportBridgeInstallerTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('import_installer', SCRIPTS / 'install_pi_import_release_bridge.py')
        self.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.installer)
        self.manifest = json.loads((SCRIPTS.parent / 'deploy/import-release-2026-10-19.json').read_text())
        self.values = {name: (SCRIPTS / name).read_text() for name in self.manifest['runners']}

    def test_only_five_fixed_commands_are_built_and_compile(self):
        commands = self.installer.fixed_commands(self.manifest, self.values)
        self.assertEqual(set(commands), {'import_release_' + mode for mode in ('inspect', 'prepare', 'apply', 'status', 'verify')})
        for command, timeout in commands.values():
            arguments = shlex.split(command)
            self.assertEqual(arguments[:2], ['python3', '-c'])
            self.assertEqual(len(arguments), 3)
            self.assertEqual(timeout, 180)
            compile(arguments[2], 'fixed bridge bootstrap', 'exec')

    def test_modified_runner_or_target_is_rejected(self):
        with self.assertRaises(AssertionError): self.installer.fixed_commands(self.manifest, {**self.values, 'pi_import_release.py': 'changed'})
        with self.assertRaises(AssertionError): self.installer.fixed_commands({**self.manifest, 'target': 'unapproved'}, self.values)

    def test_installer_manifest_is_immutable(self):
        self.assertEqual(hashlib.sha256(self.installer.MANIFEST.read_bytes()).hexdigest(), self.installer.MANIFEST_SHA256)

    def test_final_verification_requires_released_maintenance_and_http_401(self):
        for maintenance, status, permitted in [(False, 401, True), (True, 401, False), (False, 503, False)]:
            with self.subTest(maintenance=maintenance, status=status), \
                 patch.dict(sys.modules, {'app.services.maintenance': SimpleNamespace(is_maintenance_active=lambda: maintenance)}), \
                 patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError('synthetic', status, '', None, None)):
                if permitted: exec(self.installer.FINAL_ACCESS_CHECK, {})
                else:
                    with self.assertRaises(AssertionError): exec(self.installer.FINAL_ACCESS_CHECK, {})

    def test_known_runner_upgrade_requires_a_confirmed_rollback_at_the_fixed_base(self):
        command = self.installer.fixed_commands(self.manifest, self.values)['import_release_status'][0]
        program = shlex.split(command)[2]
        real_hash = hashlib.sha256
        previous_hash = self.manifest['previous_runners']['pi_import_release.py']
        def digest(data):
            return SimpleNamespace(hexdigest=lambda: previous_hash) if data == b'old-pinned-runner' else real_hash(data)
        for status, rollback_ok, head, permitted in [('running', True, release.BASE, False), ('failed', False, release.BASE, False),
                                                      ('failed', True, 'changed-base', False), ('failed', True, release.BASE, True)]:
            with self.subTest(status=status, rollback_ok=rollback_ok, head=head), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                root = Path(folder)
                control = root / '.runtime/import-release-20261019'
                control.mkdir(parents=True)
                (control / 'pi_import_release.py').write_bytes(b'old-pinned-runner')
                (control / 'pi_rollout.py').write_text(self.values['pi_rollout.py'])
                (control / 'state.json').write_text(json.dumps({'status': status, 'rollback_ok': rollback_ok}))
                local = program.replace('/home/jan/papermind', str(root))
                stack.enter_context(patch('hashlib.sha256', side_effect=digest))
                stack.enter_context(patch('subprocess.check_output', return_value=head))
                run = stack.enter_context(patch('runpy.run_path'))
                stack.enter_context(patch.object(sys, 'argv', list(sys.argv)))
                stack.enter_context(patch.object(sys, 'path', list(sys.path)))
                stack.enter_context(patch.object(sys, 'dont_write_bytecode', True))
                if permitted:
                    exec(local, {})
                    self.assertEqual((control / 'pi_import_release.py').read_text(), self.values['pi_import_release.py'])
                    run.assert_called_once()
                else:
                    with self.assertRaises(AssertionError): exec(local, {})
                    self.assertEqual((control / 'pi_import_release.py').read_bytes(), b'old-pinned-runner')
                    run.assert_not_called()

    def test_install_preserves_existing_actions_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root = Path(folder)
            bridge = root / 'bridge.py'
            original = (SCRIPTS.parent / 'infra/launchd/papermind-pi-bridge.py').read_text()
            bridge.write_text(original)
            (root / 'scripts').mkdir()
            for name, value in self.values.items(): (root / 'scripts' / name).write_text(value)
            (root / '.runtime/import-release-20261019').mkdir(parents=True)
            archive = b'synthetic test release'
            manifest = {**self.manifest, 'archive_sha256': hashlib.sha256(archive).hexdigest()}
            data = json.dumps(manifest).encode()
            manifest_path = root / 'manifest.json'
            manifest_path.write_bytes(data)
            (root / '.runtime/import-release-20261019/release-payload.json').write_text(json.dumps({
                'archive_sha256': manifest['archive_sha256'], 'archive_base64': base64.b64encode(archive).decode()}))
            for name, value in {'ROOT': root, 'BRIDGE': bridge, 'PAYLOAD': root / 'payload.json', 'MANIFEST': manifest_path,
                                'MANIFEST_SHA256': hashlib.sha256(data).hexdigest()}.items():
                stack.enter_context(patch.object(self.installer, name, value))
            stack.enter_context(patch.object(self.installer, 'fixed_commands', return_value={'import_release_inspect': ('fixed inspection', 180)}))
            stack.enter_context(patch.object(sys, 'argv', ['installer']))
            self.installer.main()
            once = bridge.read_text()
            self.installer.main()
            self.assertEqual(bridge.read_text(), once)
            self.assertIn('"scanner_status"', once)
            self.assertEqual(once.count('# BEGIN fixed October 19 import release'), 1)
            self.assertEqual(bridge.with_suffix('.before-import-release-20261019.bak').read_text(), original)
            self.assertEqual((root / 'payload.json').stat().st_mode & 0o777, 0o600)


if __name__ == '__main__': unittest.main()
