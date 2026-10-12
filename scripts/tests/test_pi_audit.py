import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


probe = module('pi_performance_probe')
audit = module('pi_audit')


class Response:
    status = 200
    headers = {}
    closed = False
    def __init__(self, data=b'private note body'):
        self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True
    def read(self, limit): return self.data[:limit]


class AuditTest(unittest.TestCase):
    def test_measurement_never_returns_tokens_body_or_document_paths(self):
        response = Response()
        with patch.object(probe.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value = response
            result = probe.read_request('notes_list', '/api/notes?limit=500', 'private-access-token')
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), 'GET')
            self.assertEqual(request.get_header('Accept-encoding'), 'gzip')
            self.assertEqual(request.get_header('Authorization'), 'Bearer private-access-token')
        output = json.dumps(result)
        self.assertNotIn('private-access-token', output)
        self.assertNotIn('private note body', output)
        self.assertNotIn('/api/notes', output)
        self.assertTrue(response.closed)
        self.assertEqual(result['status'], 200)

    def test_large_response_is_bounded_and_closed(self):
        response = Response(b'x' * (probe.MAX_BODY + 100))
        with patch.object(probe.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value = response
            result = probe.read_request('pdf_initial_range', '/api/documents/test/file', 'token', ranged=True)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header('Range'), 'bytes=0-65535')
        self.assertTrue(result['capped'])
        self.assertEqual(result['bytes'], probe.MAX_BODY)
        self.assertTrue(response.closed)

    def test_non_api_and_query_tokens_are_rejected_before_network(self):
        with patch.object(probe.urllib.request, 'build_opener') as opener:
            for path in ('https://example.invalid/api/notes', '/private', '//evil/api/notes', '/api/notes?token=secret'):
                with self.assertRaises(AssertionError):
                    probe.read_request('invalid', path, 'token')
            opener.assert_not_called()

    def test_redirect_does_not_forward_credentials(self):
        request = probe.urllib.request.Request('http://caddy/api/notes', headers={'Authorization': 'Bearer private'})
        self.assertIsNone(probe.NoRedirect().redirect_request(request, None, 302, '', {}, 'https://example.invalid/'))

    def test_http_errors_are_counted_without_returning_body(self):
        error = probe.urllib.error.HTTPError('http://caddy/api/notes', 503, 'private error', {}, io.BytesIO(b'private error body'))
        with patch.object(probe.urllib.request, 'build_opener') as opener:
            opener.return_value.open.side_effect = error
            result = probe.read_request('notes_list', '/api/notes', 'token')
        self.assertEqual(result['status'], 503)
        self.assertNotIn('private error', json.dumps(result))

    def test_connection_failure_has_only_sanitized_error_type(self):
        with patch.object(probe.urllib.request, 'build_opener') as opener:
            opener.return_value.open.side_effect = OSError('password=private')
            result = probe.read_request('notes_list', '/api/notes', 'token')
        self.assertEqual(result['error_type'], 'OSError')
        self.assertNotIn('private', json.dumps(result))

    def test_p95_interpolation_and_median(self):
        values = list(range(20))
        self.assertEqual(probe.percentile(values, .5), 9.5)
        self.assertAlmostEqual(probe.percentile(values, .95), 18.05)
        self.assertEqual(probe.percentile([17], .95), 17)

    def test_rate_limiter_reserves_nonoverlapping_slots(self):
        limiter = probe.RateLimit(2)
        with patch.object(probe.time, 'monotonic', return_value=100), patch.object(probe.time, 'sleep') as sleep:
            for _ in range(4): limiter.wait()
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0, .5, 1, 1.5])

    def test_invalid_load_mode_cannot_reach_production_setup(self):
        with patch.object(probe, 'plan') as plan:
            with self.assertRaises(AssertionError): probe.run('unbounded')
            plan.assert_not_called()

    def test_inventory_includes_held_installed_packages_and_correct_source_version(self):
        data = ('libtest:arm64\t2.1+b1\tarm64\ttest\t2.1\tii \n'
            'held\t3.0\tarm64\t\t\thi \nremoved\t1.0\tarm64\tremoved\t1.0\trc \n')
        result = audit.parse_dpkg(data)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {'name': 'libtest', 'version': '2.1+b1', 'architecture': 'arm64', 'source': 'test', 'source_version': '2.1'})
        self.assertEqual(result[1]['source_version'], '3.0')

    def test_wrong_pi_revision_aborts_before_container_or_api_calls(self):
        with patch.object(audit, 'command', return_value=subprocess.CompletedProcess([], 0, 'other-revision\n', '')), patch.object(audit, 'containers') as containers:
            with self.assertRaisesRegex(AssertionError, 'Unexpected Pi revision'): audit.preflight()
            containers.assert_not_called()

    def test_command_errors_do_not_expose_stderr_credentials(self):
        with patch.object(audit.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'password=private')):
            with self.assertRaises(RuntimeError) as error: audit.command(['docker', 'exec'])
        self.assertNotIn('private', str(error.exception))


if __name__ == '__main__':
    unittest.main()
