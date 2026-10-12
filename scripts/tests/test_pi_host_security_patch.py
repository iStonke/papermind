import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
spec=importlib.util.spec_from_file_location('host_patch',Path(__file__).parents[1]/'pi_host_security_patch.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)


class HostPlanTest(unittest.TestCase):
    def test_plan_keeps_exact_installed_and_candidate_versions(self):
        self.assertEqual(host.parse_plan('Inst openssl [3.5.6-1~deb13u2] (3.5.7-1~deb13u3 Debian:13 [arm64])\n'),
            [{'name':'openssl','old':'3.5.6-1~deb13u2','new':'3.5.7-1~deb13u3'}])

    def test_removals_unknown_dependencies_and_system_transitions_are_rejected(self):
        for plan in ('Remv openssl [3.5.6]\n','Inst new-package (1.0 Debian:13 [arm64])\n',
            'Inst linux-image [1] (2 Debian:13 [arm64])\n','Inst docker-ce [1] (2 Debian:13 [arm64])\n'):
            with self.subTest(plan=plan),self.assertRaises(AssertionError):host.parse_plan(plan)

    def test_malformed_installation_line_cannot_be_silently_omitted(self):
        with self.assertRaises(AssertionError):host.parse_plan('Inst openssl malformed\n')

    def test_preparation_before_rollout_is_limited_to_the_active_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'release.json'
            with patch.object(host.release,'STATE',state),patch.object(host.release,'preflight') as preflight,patch.object(host,'apt') as apt:
                for value in ({'status':'prepared','phase':'prepared'}, {'status':'failed','phase':'failed'},
                        {'status':'running','phase':'migrating_ownership'}):
                    state.write_text(json.dumps(value))
                    with self.subTest(state=value),self.assertRaises(AssertionError):host.plan()
                apt.assert_not_called();preflight.assert_not_called()

    def test_backup_overlap_only_prepares_a_plan_and_does_not_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'release.json';state.write_text('{"status":"running","phase":"backup"}')
            names=json.loads(Path(host.__file__).with_name('pi_host_security_packages.json').read_text())
            metadata=''.join(name+'\t1\tii \n' for name in names)
            with patch.object(host.release,'STATE',state),patch.object(host.release,'preflight') as preflight, \
                    patch.object(host,'STATE',root/'host.json'),patch.object(host,'PLAN',root/'plan.json'), \
                    patch.object(host,'installed',return_value=metadata),patch.object(host,'apt',return_value='') as apt:
                host.plan()
                preflight.assert_called_once_with(host.release.BASE)
                self.assertEqual(apt.call_count,2)
                self.assertTrue(all('-y' not in call.args for call in apt.call_args_list))
                self.assertEqual(json.loads((root/'host.json').read_text())['status'],'prepared')

    def test_failed_backup_prevents_host_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'state.json';plan=root/'plan.json'
            state.write_text('{"status":"running","phase":"starting_apply"}')
            plan.write_text(json.dumps({'head':host.release.TARGET,
                'installed_sha256':hashlib.sha256(b'installed').hexdigest(),
                'packages':[{'name':'openssl','old':'1','new':'2'}]}))
            with patch.object(host,'STATE',state),patch.object(host,'PLAN',plan), \
                    patch.object(host,'installed',return_value='installed'),patch.object(host.release,'preflight'), \
                    patch.object(host,'apt',return_value='Inst openssl [1] (2 Debian:13 [arm64])\n') as apt, \
                    patch.object(host.release.helpers,'compose',side_effect=RuntimeError('backup failed')):
                with self.assertRaises(RuntimeError):host.apply()
                apt.assert_called_once_with('verify')
                self.assertEqual(json.loads(state.read_text())['phase'],'backup')


if __name__=='__main__':unittest.main()
