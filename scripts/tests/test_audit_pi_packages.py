import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location('packages', Path(__file__).parents[1] / 'audit_pi_packages.py')
packages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packages)


class PackageAuditTest(unittest.TestCase):
    def test_dpkg_preserves_binary_and_source_versions(self):
        result = packages.dpkg_status([{'name': 'libsample', 'version': '1.0+b3', 'architecture': 'arm64',
            'source': 'sample', 'source_version': '1.0'}])
        self.assertIn('Version: 1.0+b3\nSource: sample (1.0)\n', result)
        self.assertIn('Status: install ok installed\n', result)
        with self.assertRaises(AssertionError):
            packages.dpkg_status([{'name': 'libsample', 'version': '1.0\nPackage: injected',
                'architecture': 'arm64', 'source': 'sample', 'source_version': '1.0'}])

    def test_summary_distinguishes_duplicate_binaries_from_source_advisories(self):
        def match(name, advisory, state, severity='High'):
            return {'artifact': {'name': name, 'version': '1.0+b1', 'upstreams': [{'name': 'sample', 'version': '1.0'}]},
                'vulnerability': {'id': advisory, 'severity': severity, 'fix': {'state': state, 'versions': ['1.1']}}}
        summary = packages.summarize({'matches': [match('libsample', 'CVE-fixed', 'fixed'),
            match('sample', 'CVE-fixed', 'fixed'), match('sample', 'CVE-open', 'not-fixed'),
            match('sample', 'CVE-ignored', 'wont-fix', 'Low')]})
        self.assertEqual(summary['package_matches'], 4)
        self.assertEqual(summary['unique_advisories'], 3)
        self.assertEqual(summary['fixable_priority_matches'], 2)
        self.assertEqual(summary['fixable_priority_source_advisories'], 1)
        self.assertEqual(summary['fix_state_counts'], {'fixed': 2, 'not-fixed': 1, 'wont-fix': 1})
        self.assertEqual(summary['priority_findings'][0]['source_version'], '1.0')

    def test_go_catalog_uses_runtime_and_recorded_modules_without_inventing_devel_version(self):
        catalog = packages.go_sbom('go\tgo1.26.3\nmod\tcaddy\t(devel)\ndep\tgolang.org/x/net\tv0.55.0\th1:checksum\n')
        self.assertEqual(len(catalog['components']), 2)
        self.assertEqual(catalog['components'][0]['purl'], 'pkg:golang/stdlib@1.26.3')
        self.assertEqual(catalog['components'][1]['version'], '0.55.0')

    def test_missing_go_release_and_replaced_modules_require_review(self):
        for metadata in ('dep\tx/net\tv0.55.0\n', 'go\tgo1.26.3\n=>\treplacement\tv1.0.0\n'):
            with self.assertRaises(AssertionError):
                packages.go_sbom(metadata)

    def test_package_fingerprint_ignores_install_time_but_rejects_version_changes(self):
        inventory={'targets':{'frontend':{'manager':'apk','apk_database':'P:openssl\nV:3.5.8-r0\nA:aarch64\no:openssl\nt:100\n\n'}}}
        original=packages.package_fingerprints(inventory)
        inventory['targets']['frontend']['apk_database']=inventory['targets']['frontend']['apk_database'].replace('t:100','t:200')
        self.assertEqual(packages.package_fingerprints(inventory),original)
        inventory['targets']['frontend']['apk_database']=inventory['targets']['frontend']['apk_database'].replace('3.5.8-r0','3.5.9-r0')
        self.assertNotEqual(packages.package_fingerprints(inventory),original)


if __name__ == '__main__':
    unittest.main()
