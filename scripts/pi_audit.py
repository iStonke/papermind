#!/usr/bin/env python3
"""Fixed October 12 Pi measurements and public package inventory, via bridge."""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path('/home/jan/papermind')
CONTROL = ROOT / '.runtime/pi-audit-2026-10-12-gzip'
EXPECTED_HEAD = 'acc22ca29a695cdd987624b479d90aa7aed419a3'
PROBE_SHA256 = 'dd1dd42fb885ea35c3d95807cd4ae422e497de84a870eddc9b4f0a9f46d008af'
SERVICES = ('backend', 'worker', 'ai', 'frontend', 'db', 'caddy')
DPKG_FORMAT = '${binary:Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}\t${db:Status-Abbrev}\n'


def command(args, *, timeout=20, check=True):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f'Fixed {args[0]} operation failed ({result.returncode})')
    return result


def compose(*args):
    return ['docker', 'compose', '--env-file', '.env.prod', '-f', 'docker-compose.prod.yml', *args]


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def containers():
    result = {}
    for service in SERVICES:
        identifier = command(compose('ps', '-q', service)).stdout.strip()
        assert re.fullmatch(r'[0-9a-f]{64}', identifier), 'Container missing: ' + service
        data = json.loads(command(['docker', 'inspect', '--format', '{{json .State}}', identifier]).stdout)
        assert data['Running'] and data.get('Health', {}).get('Status', 'healthy') == 'healthy', 'Unhealthy: ' + service
        image = command(['docker', 'inspect', '--format', '{{.Image}}', identifier]).stdout.strip()
        result[service] = {'id': identifier, 'image': image}
    return result


def preflight():
    assert command(['git', 'rev-parse', 'HEAD']).stdout.strip() == EXPECTED_HEAD, 'Unexpected Pi revision'
    assert not command(['git', 'status', '--porcelain', '--untracked-files=no']).stdout.strip(), 'Tracked source changes'
    probe = Path(__file__).with_name('pi_performance_probe.py').read_bytes()
    assert hashlib.sha256(probe).hexdigest() == PROBE_SHA256, 'Probe checksum mismatch'
    return containers()


def cpu_ticks():
    return [int(value) for value in Path('/proc/stat').read_text().splitlines()[0].split()[1:9]]


def resources(previous=None, observed_containers=None):
    ticks = cpu_ticks()
    memory = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line}
    sample = {'at': datetime.now(timezone.utc).isoformat(), 'available_memory_mib': round(memory['MemAvailable'] / 1024, 1)}
    if previous:
        delta = [a - b for a, b in zip(ticks, previous)]
        total = sum(delta)
        if total:
            sample['host_cpu_pct'] = round((1 - (delta[3] + delta[4]) / total) * 100, 2)
            sample['host_iowait_pct'] = round(delta[4] / total * 100, 2)
    temperature = Path('/sys/class/thermal/thermal_zone0/temp')
    if temperature.exists():
        sample['temperature_c'] = int(temperature.read_text()) / 1000
    stats = command(['docker', 'stats', '--no-stream', '--format', '{{json .}}', *[
        value['id'] for value in (observed_containers or containers()).values()]], timeout=15).stdout
    sample['containers'] = []
    for line in stats.splitlines():
        row = json.loads(line)
        sample['containers'].append({key: row[key] for key in ('Name', 'CPUPerc', 'MemUsage', 'MemPerc', 'BlockIO', 'PIDs')})
    assert sample.get('temperature_c', 0) < 80 and sample['available_memory_mib'] >= 256, 'Resource guard'
    return sample, ticks


def measure():
    initial = preflight()
    state = {'status': 'running', 'phase': 'baseline', 'head': EXPECTED_HEAD,
        'started_at': datetime.now(timezone.utc).isoformat(), 'images': {key: value['image'] for key, value in initial.items()},
        'phases': {}, 'resource_samples': []}
    state_path = CONTROL / 'performance.json'
    atomic_json(state_path, state)
    previous = None
    try:
        until = time.monotonic() + 10
        while time.monotonic() < until:
            sample, previous = resources(previous, initial)
            sample['phase'] = 'baseline'
            state['resource_samples'].append(sample)
            atomic_json(state_path, state)
            time.sleep(1)
        probe = Path(__file__).with_name('pi_performance_probe.py').read_text()
        for phase in ('normal', 'limited_load'):
            assert containers() == initial, 'Containers changed during audit'
            state['phase'] = phase
            atomic_json(state_path, state)
            with (CONTROL / 'probe-output.json').open('w') as output:
                os.chmod(output.name, 0o600)
                process = subprocess.Popen(compose('exec', '-T', 'backend', 'python', '-c', probe, phase),
                    cwd=ROOT, stdout=output, stderr=subprocess.DEVNULL)
                deadline = time.monotonic() + 210
                while process.poll() is None:
                    try:
                        assert time.monotonic() < deadline, 'Phase deadline'
                        sample, previous = resources(previous, initial)
                        sample['phase'] = phase
                        state['resource_samples'].append(sample)
                        atomic_json(state_path, state)
                        time.sleep(2)
                    except Exception:
                        process.terminate()
                        # The in-container probe independently expires at 180 seconds.
                        process.wait(timeout=10)
                        raise
                assert process.returncode == 0, 'Fixed API probe failed'
            result = json.loads((CONTROL / 'probe-output.json').read_text().splitlines()[-1])
            state['phases'][phase] = result
            assert all(row['errors'] == 0 for row in result['routes']), 'API error during audit'
        assert containers() == initial, 'Containers changed during audit'
        state.update(status='success', phase='complete', finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        state.update(status='failed', error_type=type(exc).__name__)
    atomic_json(state_path, state)


def parse_dpkg(text):
    packages = []
    for line in text.splitlines():
        fields = line.split('\t')
        if len(fields) == 6 and len(fields[5]) >= 2 and fields[5][1] == 'i':
            name, version, arch, source, source_version, _ = fields
            packages.append({'name': name.split(':')[0], 'version': version, 'architecture': arch,
                'source': source or name.split(':')[0], 'source_version': source_version or version})
    return packages


def inventory():
    initial = preflight()
    result = {'collected_at': datetime.now(timezone.utc).isoformat(), 'head': EXPECTED_HEAD,
        'kernel': command(['uname', '-r']).stdout.strip(), 'targets': {}}
    for target, metadata in {'host': None, **initial}.items():
        def run(*args, check=True):
            prefix = ['docker', 'exec', metadata['id']] if metadata else []
            return command([*prefix, *args], check=check)
        release = run('cat', '/etc/os-release').stdout
        dpkg = run('dpkg-query', '-W', '-f=' + DPKG_FORMAT, check=False)
        entry = {'os_release': release, 'image': metadata['image'] if metadata else None}
        if dpkg.returncode == 0:
            entry.update(manager='dpkg', packages=parse_dpkg(dpkg.stdout))
        else:
            apk = run('cat', '/lib/apk/db/installed', check=False)
            assert apk.returncode == 0, 'Unsupported package manager: ' + target
            entry.update(manager='apk', apk_database=apk.stdout)
        versions = {}
        tools = {'host': [('docker', 'version', '--format', '{{.Server.Version}}'), ('openssl', 'version')],
            'backend': [('python', '-VV'), ('openssl', 'version')], 'worker': [('python', '-VV'), ('openssl', 'version')],
            'ai': [('python', '-VV')], 'frontend': [('nginx', '-v')], 'db': [('postgres', '--version')],
            'caddy': [('caddy', 'build-info')]}[target]
        for args in tools:
            value = run(*args, check=False)
            if value.returncode == 0:
                versions[args[0]] = (value.stdout + value.stderr).strip()[:20000]
        entry['runtime_versions'] = versions
        if target in {'backend','worker','ai'}:
            code="import importlib.metadata as m,json;print(json.dumps(sorted((d.metadata['Name'],d.version) for d in m.distributions())))"
            packages=json.loads(run('python','-c',code).stdout)
            assert len(packages)<=250 and all(re.fullmatch(r'[A-Za-z0-9_.-]+',p[0]) and len(p[1])<=100 for p in packages), 'Python metadata bound'
            entry['python_packages']=packages
        result['targets'][target] = entry
    assert containers() == initial, 'Container inventory changed'
    raw = json.dumps(result)
    assert len(raw.encode()) < 900000, 'Inventory size bound'
    atomic_json(CONTROL / 'inventory.json', result)
    print(raw)


def main():
    CONTROL.mkdir(mode=0o700, parents=True, exist_ok=True)
    CONTROL.chmod(0o700)
    assert sys.argv[1:] in [['--start'], ['--run'], ['--status'], ['--inventory']], 'Unsupported fixed operation'
    if sys.argv[1] == '--start':
        preflight()
        with (CONTROL / 'admission.lock').open('a+') as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            state_path = CONTROL / 'performance.json'
            if state_path.exists():
                state = json.loads(state_path.read_text())
                if state.get('status') == 'running':
                    raise ValueError('Measurement already running')
                if state.get('status') == 'success':
                    print(json.dumps(state));return
            atomic_json(state_path, {'status': 'running', 'phase': 'starting'})
            with (CONTROL / 'runner.log').open('w') as log:
                os.chmod(log.name, 0o600)
                process = subprocess.Popen([sys.executable, __file__, '--run'], cwd=ROOT,
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            print(json.dumps({'status': 'started', 'pid': process.pid}))
    elif sys.argv[1] == '--run':
        try:
            measure()
        except Exception as exc:
            atomic_json(CONTROL / 'performance.json', {'status': 'failed', 'error_type': type(exc).__name__})
    elif sys.argv[1] == '--inventory':
        inventory()
    else:
        state = CONTROL / 'performance.json'
        print(state.read_text() if state.exists() else '{"status":"not_started"}')


if __name__ == '__main__':
    main()
