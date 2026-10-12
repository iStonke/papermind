#!/usr/bin/env python3
"""Local, offline SBOM scan of the fixed Pi package inventory.

The Pi only supplies public package metadata. The vulnerability database is
downloaded separately; this program uploads neither inventory nor SBOMs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote


def dpkg_status(packages):
    records = []
    for package in packages:
        assert re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', package['name']), 'Unexpected package name'
        assert all('\n' not in str(value) and '\r' not in str(value) for value in package.values()), 'Unexpected package field'
        records.append('\n'.join(['Package: ' + package['name'], 'Status: install ok installed',
            'Architecture: ' + package['architecture'], 'Version: ' + package['version'],
            'Source: ' + package['source'] + ' (' + package['source_version'] + ')',
            'Description: public Pi package inventory']) + '\n\n')
    return ''.join(records)


def summarize(data):
    matches = data.get('matches', [])
    counts = Counter(match['vulnerability']['severity'] for match in matches)
    priority = []
    for match in matches:
        vulnerability = match['vulnerability']
        artifact = match['artifact']
        if vulnerability['severity'] in {'Critical', 'High'}:
            upstream = next(iter(artifact.get('upstreams') or []), {})
            priority.append({'id': vulnerability['id'], 'severity': vulnerability['severity'],
                'package': artifact['name'], 'installed': artifact['version'],
                'source': upstream.get('name') or artifact['name'], 'source_version': upstream.get('version'),
                'fix': vulnerability.get('fix'), 'data_source': vulnerability.get('dataSource'),
                'namespace': vulnerability.get('namespace'), 'match_type': match.get('matchDetails', [{}])[0].get('type')})
    fixed_priority = [finding for finding in priority if (finding['fix'] or {}).get('state') == 'fixed']
    return {'package_matches': len(matches), 'unique_advisories': len({match['vulnerability']['id'] for match in matches}),
        'severity_counts': dict(counts),
        'fix_state_counts': dict(Counter(match['vulnerability'].get('fix', {}).get('state') or 'unknown' for match in matches)),
        'fixable_advisories': len({match['vulnerability']['id'] for match in matches
            if match['vulnerability'].get('fix', {}).get('state') == 'fixed'}),
        'fixable_priority_matches': len(fixed_priority),
        'fixable_priority_source_advisories': len({(finding['id'], finding['source']) for finding in fixed_priority}),
        'distro': data.get('distro'), 'priority_findings': priority}


def go_sbom(build_info):
    """Catalog only recorded Go runtime/modules; fail on unhandled replacements."""
    components = []
    for line in build_info.splitlines():
        fields = line.split('\t')
        assert fields[0] != '=>', 'Go replacement metadata requires review'
        if fields[0] == 'go' and len(fields) == 2:
            assert re.fullmatch(r'go\d+\.\d+\.\d+', fields[1]), 'Unrecognized Go release'
            name, version = 'stdlib', fields[1][2:]
        elif fields[0] == 'dep' and len(fields) >= 3:
            name, version = fields[1], fields[2].removeprefix('v')
            assert version and version != '(devel)', 'Unversioned Go dependency'
        else:
            continue
        components.append({'type': 'library', 'name': name, 'version': version,
            'purl': 'pkg:golang/' + quote(name, safe='/') + '@' + quote(version, safe='.-')})
    assert any(component['name'] == 'stdlib' for component in components), 'Missing Go runtime metadata'
    return {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1, 'components': components}


def scan(inventory_path, tools_path, output):
    inventory = json.loads(Path(inventory_path).read_text())
    tools = json.loads(Path(tools_path).read_text())
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = {**os.environ, 'SYFT_CHECK_FOR_APP_UPDATE': 'false', 'GRYPE_CHECK_FOR_APP_UPDATE': 'false',
        'GRYPE_DB_AUTO_UPDATE': 'false', 'GRYPE_DB_CACHE_DIR': str(Path(tools['grype']['binary']).parent / 'grype-db')}
    results = {'inventory_at': inventory['collected_at'], 'head': inventory['head'], 'kernel': inventory['kernel'],
        'tools': tools, 'targets': {}}
    for name, entry in inventory['targets'].items():
        assert name in {'host', 'backend', 'worker', 'ai', 'frontend', 'db', 'caddy'}
        directory = output / name
        rootfs = directory / 'metadata-rootfs'
        (rootfs / 'etc').mkdir(mode=0o700, parents=True, exist_ok=True)
        (rootfs / 'etc/os-release').write_text(entry['os_release'])
        if entry['manager'] == 'dpkg':
            db = rootfs / 'var/lib/dpkg'
            db.mkdir(parents=True, exist_ok=True)
            (db / 'status').write_text(dpkg_status(entry['packages']))
            cataloger = 'dpkg-db-cataloger'
            expected_count = len(entry['packages'])
        else:
            assert entry['manager'] == 'apk'
            db = rootfs / 'lib/apk/db'
            db.mkdir(parents=True, exist_ok=True)
            (db / 'installed').write_text(entry['apk_database'])
            cataloger = 'apk-db-cataloger'
            expected_count = sum(line.startswith('P:') for line in entry['apk_database'].splitlines())
        sbom = directory / 'sbom.json'
        report = directory / 'grype.json'
        with (directory / 'scan.log').open('w') as log:
            subprocess.run([tools['syft']['binary'], 'dir:' + str(rootfs), '--override-default-catalogers', cataloger,
                '-o', 'syft-json=' + str(sbom)], env=env, stdout=log, stderr=log, check=True, timeout=120)
            actual = json.loads(sbom.read_text())
            assert len(actual['artifacts']) == expected_count, 'Incomplete package catalog: ' + name
            subprocess.run([tools['grype']['binary'], 'sbom:' + str(sbom), '-o', 'json', '--file', str(report)],
                env=env, stdout=log, stderr=log, check=True, timeout=120)
        summary = summarize(json.loads(report.read_text()))
        summary.update(packages=expected_count, image=entry['image'], runtime_versions=entry['runtime_versions'])
        results['targets'][name] = summary
        (output / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
        print(json.dumps({'target': name, 'packages': expected_count, 'advisories': summary['unique_advisories'],
            'severity_counts': summary['severity_counts']}), flush=True)
    build_info = inventory['targets']['caddy']['runtime_versions']['caddy']
    sbom = output / 'caddy-go.cdx.json'
    report = output / 'caddy-go.grype.json'
    catalog = go_sbom(build_info)
    sbom.write_text(json.dumps(catalog, indent=2) + '\n')
    with (output / 'caddy-go.log').open('w') as log:
        subprocess.run([tools['grype']['binary'], 'sbom:' + str(sbom), '-o', 'json', '--file', str(report)],
            env=env, stdout=log, stderr=log, check=True, timeout=120)
    summary = summarize(json.loads(report.read_text()))
    summary.update(packages=len(catalog['components']), coverage='Recorded versions; no function reachability analysis')
    results['targets']['caddy-go'] = summary
    (output / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('inventory')
    parser.add_argument('tools')
    parser.add_argument('output')
    args = parser.parse_args()
    scan(args.inventory, args.tools, args.output)
