#!/usr/bin/env python3
"""Fixed, read-only rollout verification plus synthetic PDF/audio checks."""
import gzip
import json
import re
import subprocess
import urllib.request
from pathlib import Path

ROOT=Path('/home/jan/papermind/.runtime/pi-rollout')
SHA='8a06de418d9b7d94b9c7f775a5734e0f87bc47884e2086815c1808d19afa2dff'
CHECK='''import io,json,tempfile,uuid,urllib.request,wave
from pathlib import Path
from pypdf import PdfWriter
from app.services.document_storage import DocumentStorageService
from app.services.tts import tts_service
from app.core.config import get_settings
from app.core.production import validate_production_security
from app.db.session import AppSessionLocal,SessionLocal
from sqlalchemy import text
validate_production_security(get_settings(),AppSessionLocal)
with SessionLocal() as db:
 assert db.scalar(text("SELECT version_num FROM alembic_version"))=="113_drop_note_favorite"
try:
 urllib.request.urlopen("http://127.0.0.1:8040/api/notes?limit=1",timeout=10)
 raise AssertionError("Anonymous note access was accepted")
except urllib.error.HTTPError as e:
 assert e.code==401,e.code
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp)/"test.pdf"
 w=PdfWriter();w.add_blank_page(width=20000,height=200);w.write(str(p))
 storage=DocumentStorageService(storage_path=tmp,upload_max_bytes=100000,text_check_pages=2)
 assert storage.extract_quick_text_sample(p)[3]==1
 thumbnail=storage.create_thumbnail(uuid.uuid4(),p)
 assert thumbnail is not None
 from PIL import Image,ImageDraw,ImageFont
 with Image.open(Path(tmp)/thumbnail[0]) as image:
  assert max(image.size)<=320
 scan=Path(tmp)/"scan.pdf";searchable=Path(tmp)/"searchable.pdf"
 with Image.new("RGB",(2400,800),"white") as image:
  ImageDraw.Draw(image).text((120,250),"PAPERMIND TEST",font=ImageFont.load_default(size=160),fill="black")
  image.save(scan,format="PDF",resolution=300)
 from app.services.ocr_pipeline import run_ocr_lite,_run_ocrmypdf
 recognized=run_ocr_lite(scan,language="eng",max_long_side_px=2400)
 assert "test" in recognized.casefold(),"Isolated import OCR did not recognize the sample"
 _run_ocrmypdf(scan,searchable,language="eng",deskew=False,denoise=False,dpi_target=300,timeout_seconds=45)
 assert "test" in storage.extract_quick_text_sample(searchable)[0].casefold(),"Searchable PDF has no recognized text"
 audio=tts_service.synthesize_wav("PaperMind ist bereit.")
 with wave.open(io.BytesIO(audio)) as wav:
  frames=wav.getnframes();assert frames>0
print(json.dumps({"production_security":"ok","anonymous_notes_status":401,"isolated_pdf":"ok","native_ocr":"ok","local_piper_frames":frames}))
'''

def main():
 state=json.loads((ROOT/'state.json').read_text())
 assert state.get('status')=='success' and state['archive_sha256']==SHA,'Release is not successfully installed'
 assert re.fullmatch(r'[0-9]{8}T[0-9]{6}-[0-9a-f]{12}',state['run_id'])
 config_path=ROOT/'runs'/state['run_id']/'candidate-compose.json'
 result=subprocess.run(['docker','compose','-p','papermind','-f',str(config_path),'exec','-T','backend','python','-c',CHECK],text=True,capture_output=True,timeout=120)
 if result.returncode:
  # This fixed synthetic check does not print tokens, settings or user data.
  raise RuntimeError('Runtime verification failed: '+result.stderr[-2500:])
 checks=json.loads(result.stdout.strip().splitlines()[-1])
 config=json.loads(config_path.read_text())
 port=next(p['published'] for p in config['services']['caddy']['ports'] if p['target']==80)
 base=f'http://127.0.0.1:{port}'
 request=urllib.request.Request(base+'/',headers={'Accept-Encoding':'gzip'})
 with urllib.request.urlopen(request,timeout=15) as response:
  html=response.read(128000)
  if response.headers.get('Content-Encoding')=='gzip':html=gzip.decompress(html)
 asset=re.search(r'src="(/assets/index-[^"/]+\.js)"',html.decode()).group(1)
 request=urllib.request.Request(base+asset,headers={'Accept-Encoding':'gzip'})
 with urllib.request.urlopen(request,timeout=15) as response:
  encoding=response.headers.get('Content-Encoding');size=len(response.read(1024*1024))
  assert encoding=='gzip','Static JavaScript is not compressed'
 checks.update(static_asset_encoding=encoding,entry_transfer_bytes=size)
 print(json.dumps(checks))

if __name__=='__main__':main()
