from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError
from app.db import get_db
from app.schemas.common import ErrorResponse
from app.schemas.mobile_upload import (
    MobileUploadFilesResponse,
    MobileUploadSessionCreateRequest,
    MobileUploadSessionCreateResponse,
    MobileUploadStatusResponse,
)
from app.services.mobile_upload_service import MobileUploadService

router = APIRouter(tags=["Mobile Upload"])


@router.post(
    "/api/mobile-upload/sessions",
    response_model=MobileUploadSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a mobile upload session for QR-based iPhone uploads",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def create_mobile_upload_session(
    request: Request,
    payload: MobileUploadSessionCreateRequest | None = None,
    db: Session = Depends(get_db),
) -> MobileUploadSessionCreateResponse:
    service = MobileUploadService(db)
    parsed = payload or MobileUploadSessionCreateRequest()
    return service.create_session(
        request=request,
        max_files=parsed.maxFiles,
        target_stage_id=parsed.targetStageId,
    )


@router.get(
    "/api/mobile-upload/{session_id}/status",
    response_model=MobileUploadStatusResponse,
    summary="Read mobile upload session status",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_mobile_upload_status(
    session_id: str,
    t: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MobileUploadStatusResponse:
    service = MobileUploadService(db)
    return service.get_status(session_id=session_id, token=t)


@router.post(
    "/api/mobile-upload/{session_id}/files",
    response_model=MobileUploadFilesResponse,
    summary="Upload files into a mobile upload session",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
def upload_mobile_files(
    session_id: str,
    request: Request,
    files: list[UploadFile] = File(..., description="PDF or image files"),
    t: str | None = Query(default=None),
    x_upload_token: str | None = Header(default=None, alias="X-Upload-Token"),
    db: Session = Depends(get_db),
) -> MobileUploadFilesResponse:
    token = (t or x_upload_token or "").strip()
    if not token:
        raise BadRequestError("Upload token is required")
    service = MobileUploadService(db)
    return service.upload_files(session_id=session_id, token=token, files=files, request=request)


@router.get(
    "/m/upload/{session_id}",
    response_class=HTMLResponse,
    summary="Fallback standalone mobile upload page",
)
def get_mobile_upload_fallback_page(
    session_id: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    service = MobileUploadService(db)
    service.get_status(session_id=session_id, token=None)

    html = f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>PaperMind Scan Upload</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #f7fafc 0%, #eef2f7 100%);
      min-height: 100dvh;
      display: grid;
      place-items: center;
      padding: 20px;
      color: #0f172a;
    }}
    .card {{
      width: min(520px, 100%);
      background: #ffffff;
      border: 1px solid rgba(15, 23, 42, 0.08);
      border-radius: 18px;
      box-shadow: 0 14px 32px rgba(15, 23, 42, 0.12);
      padding: 22px;
      display: grid;
      gap: 14px;
    }}
    h1 {{
      margin: 0;
      font-size: 1.2rem;
      font-weight: 700;
    }}
    p {{
      margin: 0;
      color: rgba(15, 23, 42, 0.74);
    }}
    .btn {{
      border: none;
      border-radius: 12px;
      padding: 12px 14px;
      background: #0f172a;
      color: #ffffff;
      font-weight: 600;
      font-size: 0.95rem;
    }}
    .btn:disabled {{
      opacity: 0.55;
    }}
    .status {{
      font-size: 0.92rem;
      min-height: 1.2em;
    }}
    input[type=file] {{
      display: none;
    }}
  </style>
</head>
<body>
  <main class="card">
    <h1>PaperMind Scan Upload</h1>
    <p>Scanne Dokumente und lade sie an deinen Mac hoch.</p>
    <input id="fileInput" type="file" accept="image/*,.pdf" capture="environment" multiple />
    <button id="scanBtn" class="btn" type="button">Dokument scannen</button>
    <div id="status" class="status"></div>
  </main>
  <script>
    const sessionId = {session_id!r};
    const params = new URLSearchParams(window.location.search);
    const token = params.get('t') || '';
    const scanBtn = document.getElementById('scanBtn');
    const fileInput = document.getElementById('fileInput');
    const statusEl = document.getElementById('status');

    function setStatus(text, isError = false) {{
      statusEl.textContent = text;
      statusEl.style.color = isError ? '#b91c1c' : 'rgba(15, 23, 42, 0.82)';
    }}

    async function uploadFiles(files) {{
      if (!token) {{
        setStatus('Ungültiger Upload-Link.', true);
        return;
      }}
      const data = new FormData();
      for (const file of files) {{
        data.append('files', file);
      }}
      scanBtn.disabled = true;
      setStatus('Upload läuft...');
      try {{
        const response = await fetch(`/api/mobile-upload/${{sessionId}}/files?t=${{encodeURIComponent(token)}}`, {{
          method: 'POST',
          body: data
        }});
        const payload = await response.json().catch(() => ({{}}));
        if (!response.ok) {{
          const message = payload?.error?.message || `Upload fehlgeschlagen (${{response.status}})`;
          throw new Error(message);
        }}
        setStatus(`Fertig. ${{payload.uploaded || 0}} Datei(en) hochgeladen.`);
      }} catch (error) {{
        setStatus(error?.message || 'Upload fehlgeschlagen.', true);
      }} finally {{
        scanBtn.disabled = false;
      }}
    }}

    scanBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async () => {{
      const files = Array.from(fileInput.files || []);
      fileInput.value = '';
      if (files.length === 0) {{
        return;
      }}
      await uploadFiles(files);
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
