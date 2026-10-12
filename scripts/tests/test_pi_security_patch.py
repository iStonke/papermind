import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
spec = importlib.util.spec_from_file_location('security_patch', Path(__file__).parents[1] / 'pi_security_patch.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class SecurityReleaseTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        for name, path in {'ROOT':root, 'CONTROL':root/'control', 'STATE':root/'control/state.json',
            'SOURCE':root/'source','OLD':root/'control/old.json','NEW':root/'control/new.json'}.items():
            mock = patch.object(release,name,path);mock.start();self.addCleanup(mock.stop)
        release.CONTROL.mkdir()
        self.before = {name:{'container':name,'image':'old-'+name} for name in release.SERVICES}
        self.old = {'services':{name:{'image':'old-'+name} for name in release.SERVICES}}
        self.new = {'services':{name:{'image':'new-'+name,'build':{},'environment':{}} for name in release.SERVICES}}
        release.OLD.write_text(json.dumps(self.old));release.NEW.write_text(json.dumps(self.new))
        (release.CONTROL/'candidate-inventory.json').write_text(json.dumps({'head':release.TARGET,
            'targets':{name:{'image':'id-'+name} for name in release.SERVICES}}))
        (release.CONTROL/'original-ca.json').write_text('{"sha256":"public-cert-digest"}')
        release.STATE.write_text(json.dumps({'phase':'starting_apply','status':'running','before':self.before}))
        self.events = []

    def compose(self, path, *args, **kwargs):
        self.events.append(('compose',path,*args))
        if release.BACKUP in args:return '{"verified_encrypted":true}'
        return ''

    def command(self, args, **kwargs):
        self.events.append(('command',*args))
        if args in (['git','rev-parse','HEAD'],['git','rev-parse',release.TARGET]):return release.TARGET
        if args[:3]==['docker','image','inspect']:return 'id-'+args[-1].removeprefix('new-')
        if 'sha256sum' in args:return 'public-cert-digest  root.crt'
        return ''

    def contexts(self):
        from contextlib import ExitStack
        stack=ExitStack()
        stack.enter_context(patch.object(release,'preflight',return_value=self.before))
        stack.enter_context(patch.object(release,'package_fingerprints',return_value=release.APPROVED_PACKAGES))
        stack.enter_context(patch.object(release.helpers,'compose',side_effect=self.compose))
        stack.enter_context(patch.object(release.helpers,'command',side_effect=self.command))
        stack.enter_context(patch.object(release.time,'sleep'))
        return stack

    def test_backup_failure_never_stops_or_changes_production(self):
        with self.contexts(), patch.object(release,'change_ownership') as ownership:
            with patch.object(release.helpers,'compose',side_effect=RuntimeError('backup failed')):
                with self.assertRaises(RuntimeError):release.apply()
            ownership.assert_not_called()
        state=json.loads(release.STATE.read_text())
        self.assertTrue(state['rollback_ok'])
        self.assertFalse(any('stop' in row or 'reset' in row for row in self.events))

    def test_unknown_container_change_aborts_before_backup(self):
        with patch.object(release,'preflight',return_value={}), patch.object(release.helpers,'compose') as compose:
            with self.assertRaises(AssertionError):release.apply()
            compose.assert_not_called()

    def test_success_orders_backup_drain_ownership_database_and_health(self):
        with self.contexts(), patch.object(release,'change_ownership',side_effect=lambda *a,**k:self.events.append(('ownership',k))):
            release.apply()
        backup=next(i for i,row in enumerate(self.events) if release.BACKUP in row)
        stop=next(i for i,row in enumerate(self.events) if 'stop' in row)
        ownership=next(i for i,row in enumerate(self.events) if row[0]=='ownership')
        db_start=next(i for i,row in enumerate(self.events) if 'up' in row and row[-1]=='db')
        health=next(i for i,row in enumerate(self.events) if release.helpers.VERIFY in row)
        self.assertLess(backup,stop);self.assertLess(stop,ownership);self.assertLess(ownership,db_start);self.assertLess(db_start,health)
        self.assertEqual(json.loads(release.STATE.read_text())['status'],'success')

    def test_database_failure_restores_ownership_and_fixed_git_base(self):
        original=self.compose
        def failing(path,*args,**kwargs):
            if path==release.NEW and 'up' in args and args[-1]=='db':raise RuntimeError('database candidate failed')
            return original(path,*args,**kwargs)
        with self.contexts(), patch.object(release.helpers,'compose',side_effect=failing), patch.object(release,'change_ownership') as ownership:
            with self.assertRaises(RuntimeError):release.apply()
        self.assertEqual(ownership.call_args_list[-1].kwargs,{'restore':True})
        self.assertIn(('command','git','reset','--hard',release.BASE),self.events)
        self.assertTrue(json.loads(release.STATE.read_text())['rollback_ok'])

    def test_build_failure_has_no_stop_or_git_mutation(self):
        with self.contexts(), patch.object(release.helpers,'read_config',side_effect=[self.old,self.new]), \
            patch.object(release.helpers.shutil,'disk_usage') as usage, \
            patch.object(release.helpers,'compose',side_effect=RuntimeError('build failed')):
            usage.return_value.free=20*1024**3
            with self.assertRaises(RuntimeError):release.prepare()
        self.assertFalse(any('stop' in row or 'merge' in row or 'reset' in row for row in self.events))

    def test_free_arguments_are_rejected(self):
        with patch.object(sys,'argv',['runner','--apply','arbitrary-command']), patch.object(release,'apply') as apply:
            with self.assertRaises(ValueError):release.main()
            apply.assert_not_called()


if __name__=='__main__':unittest.main()
