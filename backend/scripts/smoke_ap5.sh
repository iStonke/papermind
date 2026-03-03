#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8040}"
COMPOSE_BIN="${COMPOSE_BIN:-docker compose}"
API_VIA_COMPOSE="${API_VIA_COMPOSE:-false}"

extract_json_field() {
  local field_path="$1"
  python3 -c "import json,sys; data=json.load(sys.stdin); obj=data
for key in '$field_path'.split('.'):
    obj=obj[key]
print(obj)"
}

assert_document_in_list() {
  local payload="$1"
  local expected_doc_id="$2"
  python3 - "$expected_doc_id" "$payload" <<'PY'
import json
import sys

expected = sys.argv[1]
payload = json.loads(sys.argv[2])
items = payload.get("items", [])
if not any(item.get("id") == expected for item in items):
    print(f"expected document {expected} not found in response")
    sys.exit(1)
PY
}

assert_total_positive() {
  local payload="$1"
  python3 - "$payload" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
if int(payload.get("total", 0)) < 1:
    print("expected total >= 1")
    sys.exit(1)
PY
}

api_call() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local url="${BASE_URL}${path}"

  if [[ "$API_VIA_COMPOSE" == "true" ]]; then
    $COMPOSE_BIN exec -T backend python - "$method" "$url" "$body" <<'PY'
import json
import sys
import urllib.request

method = sys.argv[1]
url = sys.argv[2]
body = sys.argv[3]
data = body.encode("utf-8") if body else None
headers = {"Content-Type": "application/json"} if body else {}
req = urllib.request.Request(url, data=data, headers=headers, method=method)
with urllib.request.urlopen(req, timeout=10) as resp:
    print(resp.read().decode("utf-8"), end="")
PY
    return
  fi

  if [[ -n "$body" ]]; then
    curl -fsS -X "$method" "$url" -H 'Content-Type: application/json' -d "$body"
  else
    curl -fsS -X "$method" "$url"
  fi
}

UNIQ="$(date +%s)"
DOC_DATE="$(date +%F)"
FILENAME="ap5-smoke-${UNIQ}.pdf"
NOTES_TOKEN="ap5-notes-${UNIQ}"
OCR_TOKEN="ap5-ocr-${UNIQ}"
DOC_ID=""

cleanup() {
  if [[ -n "$DOC_ID" ]]; then
    api_call DELETE "/api/documents/$DOC_ID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "[1/6] create AP5 document fixture"
DOC_JSON="$(api_call POST "/api/documents" "{\"original_filename\":\"$FILENAME\",\"notes\":\"$NOTES_TOKEN\",\"document_date\":\"$DOC_DATE\"}")"
DOC_ID="$(printf '%s' "$DOC_JSON" | extract_json_field 'id')"
echo "document_id=$DOC_ID"

echo "[2/6] search by filename token"
SEARCH_FILENAME_JSON="$(api_call GET "/api/documents?q=$FILENAME&limit=20&offset=0")"
assert_document_in_list "$SEARCH_FILENAME_JSON" "$DOC_ID"

echo "[3/6] inject OCR text_content and verify OCR-token search"
$COMPOSE_BIN exec -T db sh -lc \
  "psql -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -c \"UPDATE documents SET text_content='${OCR_TOKEN} volltext' WHERE id='${DOC_ID}';\" >/dev/null"
SEARCH_OCR_JSON="$(api_call GET "/api/documents?q=$OCR_TOKEN&limit=20&offset=0")"
assert_document_in_list "$SEARCH_OCR_JSON" "$DOC_ID"

echo "[4/6] search with status/date filters"
FILTER_JSON="$(api_call GET "/api/documents?q=$NOTES_TOKEN&status=imported&date_from=$DOC_DATE&date_to=$DOC_DATE&limit=20&offset=0")"
assert_document_in_list "$FILTER_JSON" "$DOC_ID"

echo "[5/6] reset search (normal listing)"
LIST_JSON="$(api_call GET "/api/documents?limit=5&offset=0")"
assert_total_positive "$LIST_JSON"

echo "[6/6] AP5 smoke test passed"
