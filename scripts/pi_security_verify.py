#!/usr/bin/env python3
"""Verify the installed fixed release without changing user documents."""
import json
import gzip
import http.client
import os
import re
import socket
import ssl
import subprocess
import sys

import pi_audit as audit
import pi_security_patch as release
from pi_rollout_verify import CHECK


def configure():
    state=json.loads(release.STATE.read_text())
    assert state.get('status')=='success' and state['head']==release.TARGET
    running=release.preflight(release.TARGET)
    for name in release.SERVICES:
        expected='999' if name=='db' else '1000'
        uid=release.helpers.command(['docker','exec',running[name]['container'],'id','-u'],log=False).strip()
        assert uid==expected, 'Unexpected runtime UID: '+name
        caps=release.helpers.command(['docker','exec',running[name]['container'],'cat','/proc/1/status'],log=False)
        assert 'CapEff:\t0000000000000000' in caps, 'Unexpected effective capability: '+name
    audit.EXPECTED_HEAD=release.TARGET
    audit.CONTROL=release.CONTROL/'verification'
    audit.CONTROL.mkdir(parents=True,exist_ok=True,mode=0o700)
    return running


def https_checks(running):
    """Fixed local TLS requests, verified against the preserved PaperMind CA."""
    ca=release.helpers.command(['docker','exec',running['caddy']['container'],'cat',
        '/data/caddy/pki/authorities/local/root.crt'],log=False)
    context=ssl.create_default_context(cadata=ca)
    config=json.loads(release.NEW.read_text())
    port=int(next(p['published'] for p in config['services']['caddy']['ports'] if p['target']==443))
    assert 1<=port<=65535
    def request(path,limit):
        with socket.create_connection(('127.0.0.1',port),timeout=10) as connection:
            with context.wrap_socket(connection,server_hostname='papermind') as stream:
                stream.sendall(('GET '+path+' HTTP/1.1\r\nHost: papermind\r\nAccept-Encoding: gzip\r\nConnection: close\r\n\r\n').encode())
                response=http.client.HTTPResponse(stream);response.begin();body=response.read(limit+1)
                assert len(body)<=limit, 'Fixed response size bound'
                return response.status,response.getheader('Content-Encoding','identity'),body
    status,encoding,html=request('/',131072);assert status==200
    if encoding=='gzip':html=gzip.decompress(html)
    assert len(html)<=131072
    asset=re.search(r'src="(/assets/index-[A-Za-z0-9_-]{1,100}\.js)"',html.decode()).group(1)
    status,encoding,body=request(asset,1024*1024);assert status==200 and encoding=='gzip'
    status,_,_=request('/api/notes?limit=1',8192);assert status==401
    return {'https_verified_hostname':'papermind','https_status':200,
        'static_asset_encoding':encoding,'entry_transfer_bytes':len(body),'proxy_anonymous_notes_status':status}


def main():
    running=configure()
    if sys.argv[1:]==['--inventory']:
        audit.inventory()
    elif sys.argv[1:]==['--measure']:
        path=audit.CONTROL/'performance.json'
        if path.exists():
            assert json.loads(path.read_text()).get('status') not in {'running','success'}, 'Measurement already admitted'
        audit.atomic_json(path,{'status':'running','phase':'starting'})
        with (audit.CONTROL/'measurement.log').open('w') as log:
            os.chmod(log.name,0o600)
            process=subprocess.Popen([sys.executable,__file__,'--run-measure'],cwd=release.ROOT,
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        print(json.dumps({'status':'started','pid':process.pid}))
    elif sys.argv[1:]==['--run-measure']:
        audit.measure()
    elif sys.argv[1:]==['--runtime']:
        output=release.helpers.compose(release.NEW,'exec','-T','backend','python','-c',CHECK,log=False,timeout=120)
        checks=json.loads(output.strip().splitlines()[-1])
        checks['runtime_uids']='verified';checks['effective_capabilities']='none'
        checks.update(https_checks(running))
        print(json.dumps(checks))
    elif sys.argv[1:]==['--status']:
        path=audit.CONTROL/'performance.json'
        print(path.read_text() if path.exists() else '{"status":"not_started"}')
    else:raise ValueError('Unsupported fixed verification operation')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'failed','error_type':type(exc).__name__}));raise SystemExit(1)
