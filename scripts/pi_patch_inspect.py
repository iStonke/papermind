#!/usr/bin/env python3
"""Fixed read-only preparation for the authorized October 12 security release."""
import json
import os
from pathlib import Path
import signal
import subprocess

ROOT = Path('/home/jan/papermind')
EXPECTED_HEAD = 'acc22ca29a695cdd987624b479d90aa7aed419a3'

PROFILE = r'''
import json,time
from sqlalchemy import event,select,text
from app.db.session import SessionLocal,AppSessionLocal
from app.models.user import User
from app.services.document_query_service import DocumentQueryService
from app.schemas.documents import DocumentSortField,SortOrder

def numeric_plan(plan):
 keys={'Node Type','Relation Name','Index Name','Actual Total Time','Actual Rows','Actual Loops','Shared Hit Blocks','Shared Read Blocks','Sort Method','Sort Space Used'}
 result={k:v for k,v in plan.items() if k in keys}
 if 'Plans' in plan:result['Plans']=[numeric_plan(p) for p in plan['Plans']]
 return result

with SessionLocal() as db:
 db.execute(text('SET TRANSACTION READ ONLY'))
 owner=db.scalar(select(User.id).where(User.is_admin.is_(True),User.is_active.is_(True)).limit(1))
 assert owner is not None
reports=[]
for term in ('Rechnung','Test','paperminddiagnoseohnetreffer'):
 with AppSessionLocal() as db:
  db.info['owner_id']=str(owner)
  db.execute(text('SET TRANSACTION READ ONLY'))
  db.execute(text("SET LOCAL statement_timeout='5s'"))
  connection=db.connection();captured=[];pending={}
  def before(conn,cursor,sql,parameters,context,many):pending[id(context)]=(sql,parameters,time.perf_counter())
  def after(conn,cursor,sql,parameters,context,many):
   query,params,started=pending.pop(id(context));captured.append((query,params,(time.perf_counter()-started)*1000))
  event.listen(connection,'before_cursor_execute',before);event.listen(connection,'after_cursor_execute',after)
  started=time.perf_counter()
  result=DocumentQueryService(db,owner).list_documents(q=term,tag=None,tag_ids=None,untagged=False,status=None,
   date_from=None,date_to=None,recent_imports=False,sort=DocumentSortField.created_at,order=SortOrder.desc,limit=20,offset=0)
  elapsed=(time.perf_counter()-started)*1000
  event.remove(connection,'before_cursor_execute',before);event.remove(connection,'after_cursor_execute',after)
  timings=[]
  for sql,params,ms in captured:
   category='search_with_snippet' if 'ts_headline(' in sql else 'count' if 'count(' in sql else 'relations'
   row={'category':category,'cursor_ms':round(ms,3)}
   if sql.lstrip().upper().startswith('SELECT'):
    plan=connection.exec_driver_sql('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+sql,params).scalar()[0]
    row.update(execution_ms=plan['Execution Time'],planning_ms=plan['Planning Time'],plan=numeric_plan(plan['Plan']))
   timings.append(row)
  reports.append({'query':term,'items':len(result.items),'total':result.total,'service_ms':round(elapsed,3),'queries':timings})
 time.sleep(1)
print(json.dumps(reports))
'''


def command(args):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, 'Fixed inspection failed: ' + args[0]
    return result.stdout.strip()


def main():
    signal.alarm(180)
    assert command(['git', 'rev-parse', 'HEAD']) == EXPECTED_HEAD, 'Pi revision changed'
    assert not command(['git', 'status', '--porcelain', '--untracked-files=no']), 'Tracked source changed'
    result = {'head': EXPECTED_HEAD, 'host_uid': os.getuid(), 'host_gid': os.getgid(),
        'profile': json.loads(command(['docker', 'compose', '--env-file', '.env.prod', '-f',
            'docker-compose.prod.yml', 'exec', '-T', 'backend', 'python', '-c', PROFILE])), 'mounts': {}}
    for name in ('backend', 'worker', 'ai', 'frontend', 'db', 'caddy'):
        identifier = command(['docker', 'compose', '--env-file', '.env.prod', '-f', 'docker-compose.prod.yml', 'ps', '-q', name])
        state = json.loads(command(['docker', 'inspect', '--format', '{{json .State}}', identifier]))
        assert state['Running'] and state.get('Health', {}).get('Status', 'healthy') == 'healthy'
        mounts = json.loads(command(['docker', 'inspect', '--format', '{{json .Mounts}}', identifier]))
        result['mounts'][name] = []
        for mount in mounts:
            path = Path(mount['Source'])
            try:
                info = path.stat()
                uid, gid, mode = info.st_uid, info.st_gid, oct(info.st_mode & 0o777)
            except PermissionError:
                fields = command(['docker', 'exec', identifier, 'stat', '-c', '%u:%g:%a', mount['Destination']]).split(':')
                uid, gid, mode = int(fields[0]), int(fields[1]), oct(int(fields[2], 8))
            result['mounts'][name].append({'type': mount['Type'], 'destination': mount['Destination'],
                'uid': uid, 'gid': gid, 'mode': mode, 'writable': mount['RW']})
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
