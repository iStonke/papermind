import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('root_security',Path(__file__).parents[1]/'pi_host_security_root.py')
root=importlib.util.module_from_spec(spec);spec.loader.exec_module(root)


class RootSecurityTest(unittest.TestCase):
    def test_selection_is_the_reviewed_fixed_list(self):
        self.assertEqual(root.PACKAGES,json.loads(Path(root.__file__).with_name('pi_host_security_packages.json').read_text()))

    def test_new_packages_removals_and_system_transitions_are_rejected(self):
        for output in ('Inst new-package (1.0 Debian:13 [arm64])\n','Remv openssl [1]\n',
                'Inst openssh-server [1] (2 Debian:13 [arm64])\n','Inst systemd [1] (2 Debian:13 [arm64])\n'):
            with self.subTest(output=output),self.assertRaises(AssertionError):root.parse(output)

    def test_invalid_version_cannot_become_an_apt_option(self):
        with self.assertRaises(AssertionError):root.parse('Inst openssl [1] (--allow-unauthenticated Debian:13 [arm64])\n')

    def test_no_caller_parameters_or_unprivileged_invocation(self):
        for arguments,uid in ((['helper','install','extra'],0),(['helper','arbitrary'],0),(['helper','install'],1000)):
            with patch.object(sys,'argv',arguments),patch.object(root.os,'getuid',return_value=uid),patch.object(root,'run') as run:
                with self.subTest(arguments=arguments,uid=uid),self.assertRaises(AssertionError):root.main()
                run.assert_not_called()

    def test_changed_installed_packages_aborts_before_apt(self):
        with tempfile.TemporaryDirectory() as directory:
            plan=Path(directory)/'plan.json';plan.write_text(json.dumps({'installed_sha256':'different','packages':[]}))
            with patch.object(root,'PLAN',plan),patch.object(root,'installed',return_value='metadata'),patch.object(root,'apt') as apt:
                with self.assertRaises(AssertionError):root.run('install')
                apt.assert_not_called()

    def test_changed_simulation_aborts_before_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            plan=Path(directory)/'plan.json';plan.write_text(json.dumps({'installed_sha256':hashlib.sha256(b'metadata').hexdigest(),
                'packages':[{'name':'openssl','old':'1','new':'2'}]}))
            with patch.object(root,'PLAN',plan),patch.object(root,'installed',return_value='metadata'), \
                    patch.object(root,'apt',return_value='Inst openssl [1] (3 Debian:13 [arm64])\n') as apt:
                with self.assertRaises(AssertionError):root.run('install')
                self.assertEqual(apt.call_count,1)
                self.assertIn('--simulate',apt.call_args.args)


if __name__=='__main__':unittest.main()
