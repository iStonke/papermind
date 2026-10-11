import base64
import ast
import hashlib
import hmac
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('rollout',Path(__file__).parents[1]/'pi_rollout.py')
rollout=importlib.util.module_from_spec(spec);spec.loader.exec_module(rollout)
def release_fixture():
    buffer=io.BytesIO()
    names=['docker-compose.prod.yml','backend/Dockerfile','worker/Dockerfile','ai/Dockerfile',
           'frontend/Dockerfile.prod',f'backend/alembic/versions/{rollout.TARGET_REVISION}.py']
    with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
        for name in names:
            member=tarfile.TarInfo(name);member.size=4;archive.addfile(member,io.BytesIO(b'code'))
    return buffer.getvalue()


class ReleaseTest(unittest.TestCase):
    def test_approved_archive_is_verified_and_unpacked(self):
        archive=release_fixture()
        digest=hashlib.sha256(archive).hexdigest()
        raw=json.dumps({'archive_base64':base64.b64encode(archive).decode(),'archive_sha256':digest})
        with patch.object(rollout,'ARCHIVE_SHA256',digest):
            self.assertEqual(rollout.load_release(raw),archive)
        with tempfile.TemporaryDirectory() as directory:
            names=rollout.unpack(archive,Path(directory))
            self.assertEqual(len(names),6)
            self.assertIn(f'backend/alembic/versions/{rollout.TARGET_REVISION}.py',names)
            self.assertNotIn('.env.prod',names)

    def test_modified_release_and_extra_fields_are_rejected(self):
        for payload in [
            {'archive_base64':base64.b64encode(b'changed').decode(),'archive_sha256':rollout.ARCHIVE_SHA256},
            {'archive_base64':'','archive_sha256':rollout.ARCHIVE_SHA256,'command':'anything'},
        ]:
            with self.assertRaises(ValueError):rollout.load_release(json.dumps(payload))

    def test_traversal_links_and_secret_members_are_rejected(self):
        for name,kind in [('../escape',tarfile.REGTYPE),('/escape',tarfile.REGTYPE),('.env.prod',tarfile.REGTYPE),('backend/link',tarfile.SYMTYPE)]:
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
                member=tarfile.TarInfo(name);member.type=kind
                archive.addfile(member,io.BytesIO(b''))
            with tempfile.TemporaryDirectory() as directory,self.assertRaises(ValueError):
                rollout.unpack(buffer.getvalue(),Path(directory))

class BackupVerificationTest(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.directory=Path(temporary.name)
        self.key=b'backup-test-key'
        self.now=datetime(2026,10,11,21,30,tzinfo=timezone.utc)
        self.started=self.now-timedelta(minutes=20)
        self.manifest={
            'encrypted':True,'created_at':self.started.isoformat(),'stamp':'2026-10-11_211000',
            'database':{'alembic_revision':'111_note_pins'},'artifacts':[],
        }
        for name in ('database.dump.enc','storage.tar.gz.enc'):
            data=b'encrypted fixture '+name.encode();(self.directory/name).write_bytes(data)
            self.manifest['artifacts'].append({'filename':name,'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        self.run=SimpleNamespace(status='success',kind='manual',started_at=self.started,finished_at=self.now-timedelta(minutes=1),location='primary:'+chr(92)+'backup'+chr(92)+self.manifest['stamp'])
        self.sign()
        namespace={'json':json,'datetime':datetime,'timedelta':timedelta,'hmac':hmac,
                   'manifest_hmac':self.signature,'sha256_file':lambda p:hashlib.sha256(p.read_bytes()).hexdigest()}
        helper=next(node for node in ast.parse(rollout.BACKUP).body if isinstance(node,ast.FunctionDef))
        exec(compile(ast.Module(body=[helper],type_ignores=[]),'<backup verification>','exec'),namespace)
        self.verify=namespace['verify_preserved_backup']

    @staticmethod
    def signature(manifest,key):
        return hmac.new(key,json.dumps(manifest,sort_keys=True).encode(),'sha256').hexdigest()

    def sign(self):
        unsigned={k:v for k,v in self.manifest.items() if k!='hmac_sha256'}
        self.manifest['hmac_sha256']=self.signature(unsigned,self.key)
        (self.directory/'manifest.json').write_text(json.dumps(self.manifest))
        self.run.size_bytes=sum(p.stat().st_size for p in self.directory.iterdir())

    def check(self):
        self.verify(self.directory,self.run,self.key,'111_note_pins',self.now)

    def test_uploaded_recent_signed_backup_is_verified(self):
        self.check()

    def test_scheduled_backup_requires_success_before_acceptance(self):
        self.run.kind='scheduled';self.check()
        self.run.status='running'
        with self.assertRaises(AssertionError):self.check()

    def test_unfinished_stale_or_future_backup_is_rejected(self):
        for status,started in [('running',self.started),('success',self.now-timedelta(hours=2)),('success',self.now+timedelta(minutes=1))]:
            with self.subTest(status=status,started=started):
                self.run.status=status;self.run.started_at=started
                with self.assertRaises(AssertionError):self.check()

    def test_modified_artifact_and_manifest_are_rejected(self):
        artifact=self.directory/'database.dump.enc';original=artifact.read_bytes()
        artifact.write_bytes(b'x'*len(original))
        with self.assertRaises(AssertionError):self.check()
        artifact.write_bytes(original)
        self.manifest['created_at']=(self.started+timedelta(seconds=1)).isoformat()
        (self.directory/'manifest.json').write_text(json.dumps(self.manifest))
        with self.assertRaises(AssertionError):self.check()

    def test_other_schema_or_backup_location_is_rejected(self):
        self.manifest['database']['alembic_revision']='old';self.sign()
        with self.assertRaises(AssertionError):self.check()
        self.manifest['database']['alembic_revision']='111_note_pins';self.sign()
        self.run.location='primary:'+chr(92)+'another'
        with self.assertRaises(AssertionError):self.check()

    def test_artifact_symlink_is_rejected(self):
        artifact=self.directory/'database.dump.enc';target=self.directory/'outside';target.write_bytes(artifact.read_bytes())
        artifact.unlink();artifact.symlink_to(target)
        with self.assertRaises(AssertionError):self.check()

class RolloutTest(unittest.TestCase):
    def scenario(self,fail_at=None):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        root=Path(directory.name);control=root/'.runtime/pi-rollout';control.mkdir(parents=True)
        run=control/'runs/test';source=run/'source';source.mkdir(parents=True)
        for name,data in [('backend/app/main.py','new'),('docker-compose.prod.yml','new'),('deploy/Caddyfile','new'),('backend/alembic/versions/110_note_text_no_image_names.py','revision')]:
            p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
        live=root/'backend/app/main.py';live.parent.mkdir(parents=True);live.write_text('old')
        (root/'docker-compose.prod.yml').write_text('old')
        caddy=root/'deploy/Caddyfile';caddy.parent.mkdir();caddy.write_text('old')
        caddy_inode=caddy.stat().st_ino
        state=control/'state.json';state.write_text(json.dumps({'run_id':'test','status':'running'}))
        config={'name':'papermind','services':{s:{'build':{'context':'.'},'environment':{}} for s in rollout.SERVICES}}
        events=[]
        def command(args,**kwargs):
            events.append(('command',tuple(args)))
            if args[:2]==['git','rev-parse']:return rollout.BASE_COMMIT
            if 'inspect' in args:return 'sha256:old'
            if 'ps' in args:return 'container'
            return ''
        def compose(path,*args,**kwargs):
            events.append(('compose',Path(path).name,args))
            if args[:1]==('build',) and fail_at=='build':raise RuntimeError('synthetic build failure')
            if args[-1:]==(rollout.PREFLIGHT,) and fail_at=='preflight':raise RuntimeError('synthetic preflight failure')
            if args[-1:]==(rollout.REVISION,):return '110_note_text_no_image_names'
            if args[-1:]==(rollout.BACKUP,):return '{"backup_id":"test","status":"success","bytes":100}'
            if args[-3:]==('upgrade','head') and fail_at=='migration':raise RuntimeError('synthetic migration failure')
            if 'upgrade' in args and fail_at=='migration':raise RuntimeError('synthetic migration failure')
            return ''
        with patch.multiple(rollout,ROOT=root,CONTROL=control,STATE=state,LOG=control/'log'),patch.object(rollout,'read_config',side_effect=lambda _:json.loads(json.dumps(config))),patch.object(rollout,'command',side_effect=command),patch.object(rollout,'compose',side_effect=compose),patch.object(rollout.shutil,'disk_usage',return_value=type('Usage',(),{'free':10*1024**3})()),patch.object(rollout.time,'sleep'):
            rollout.run_rollout()
        self.assertEqual(caddy.stat().st_ino,caddy_inode,'Caddy bind mount keeps its original inode')
        return json.loads(state.read_text()),events,live.read_text()

    def test_build_failure_never_stops_live_services_or_publishes_source(self):
        state,events,content=self.scenario('build')
        self.assertEqual(state['status'],'failed');self.assertTrue(state['rollback_ok']);self.assertEqual(content,'old')
        self.assertFalse(any(e[0]=='compose' and e[2][0]=='stop' for e in events))

    def test_preflight_failure_preserves_live_version(self):
        state,events,content=self.scenario('preflight')
        self.assertEqual(state['status'],'failed');self.assertEqual(content,'old')
        self.assertFalse(any(e[0]=='compose' and e[2][-1:]==(rollout.BACKUP,) for e in events))

    def test_migration_failure_downgrades_before_restarting_old_images(self):
        state,events,content=self.scenario('migration')
        self.assertEqual(state['status'],'failed');self.assertTrue(state['rollback_ok']);self.assertEqual(content,'old')
        downgrade=next(i for i,e in enumerate(events) if e[0]=='compose' and 'downgrade' in e[2])
        restart=next(i for i,e in enumerate(events) if e[0]=='compose' and e[1]=='previous-compose.json' and e[2][0]=='up')
        self.assertLess(downgrade,restart)

    def test_success_builds_and_backs_up_before_switching(self):
        state,events,content=self.scenario()
        self.assertEqual(state['status'],'success');self.assertEqual(content,'new')
        builds=[i for i,e in enumerate(events) if e[0]=='compose' and e[2][0]=='build']
        backup=next(i for i,e in enumerate(events) if e[0]=='compose' and e[2][-1:]==(rollout.BACKUP,))
        stop=next(i for i,e in enumerate(events) if e[0]=='compose' and e[2][0]=='stop')
        self.assertEqual(len(builds),4);self.assertLess(max(builds),backup);self.assertLess(backup,stop)
        self.assertEqual(events[backup][2][:5],('run','--rm','--no-deps','--name','papermind-rollout-backup'))
        self.assertTrue(any(e[0]=='command' and rollout.RELEASE in e[1] for e in events))

if __name__=='__main__':unittest.main()
