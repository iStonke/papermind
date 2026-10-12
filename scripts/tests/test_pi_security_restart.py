import sys
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import pi_security_restart as restart


def ready_checks():
    return dict(service_active=True, service_root=True, service_script_ok=True,
        service_directory_ok=True, backup_verified=True, backup_success=True,
        schema_ok=True, power_available=True, command_path_ok=True, host_complete=True,
        backup_age_seconds=60, active_jobs=0, active_backups=0, maintenance_active=False,
        command_file_present=False, pending_action=None, already_requested=False)


class RestartGateTest(unittest.TestCase):
    def test_missing_backup_and_each_active_or_unavailable_gate_block_reboot(self):
        self.assertEqual(restart.validate(ready_checks()), [])
        for name, value in dict(backup_verified=False, backup_success=False,
                backup_age_seconds=86401, active_jobs=1, active_backups=1,
                maintenance_active=True, command_file_present=True,
                pending_action='poweroff', already_requested=True, service_active=False,
                service_root=False, service_script_ok=False, service_directory_ok=False,
                power_available=False, command_path_ok=False, schema_ok=False,
                host_complete=False).items():
            checks=ready_checks();checks[name]=value
            with self.subTest(gate=name):self.assertIn(name,restart.validate(checks))

    def test_failed_readiness_does_not_write_admission_or_request_power(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'state.json'
            with patch.object(restart.release,'CONTROL',Path(directory)), \
                    patch.object(restart,'STATE',state), \
                    patch.object(restart,'readiness',return_value={'ready':False}), \
                    patch.object(restart.release.helpers,'compose') as compose:
                with self.assertRaises(AssertionError):restart.request()
                self.assertFalse(state.exists());compose.assert_not_called()

    def test_revision_change_is_rejected_before_any_service_or_application_check(self):
        with patch.object(restart.release,'preflight',side_effect=AssertionError('Pi source revision changed')), \
                patch.object(restart,'control_checks') as controls,patch.object(restart,'application_checks') as application:
            with self.assertRaises(AssertionError):restart.readiness()
            controls.assert_not_called();application.assert_not_called()

    def test_existing_admission_prevents_second_request_even_if_other_checks_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'restart.json';state.write_text('{}')
            host=root/'host.json';host.write_text(json.dumps({'status':'success',
                'backup':{'verified_encrypted':True,'backup_id':'3b21f40c-6881-4cdc-b392-58d6802e3155'}}))
            checks=ready_checks();checks.pop('already_requested')
            with patch.object(restart,'STATE',state),patch.object(restart,'HOST_STATE',host), \
                    patch.object(restart.release,'CONTROL',root),patch.object(restart.release,'preflight'), \
                    patch.object(restart,'control_checks',return_value={}), \
                    patch.object(restart,'application_checks',return_value=checks), \
                    patch.object(restart.release.helpers,'compose') as compose:
                with self.assertRaises(AssertionError):restart.request()
                self.assertEqual(state.read_text(),'{}');compose.assert_not_called()


if __name__=='__main__':unittest.main()
