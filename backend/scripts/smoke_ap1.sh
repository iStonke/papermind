#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

extract_json_field() {
  local field_path="$1"
  python3 -c "import json,sys; data=json.load(sys.stdin); keys='$field_path'.split('.');
obj=data
for k in keys:
    obj=obj[k]
print(obj)"
}

echo "[1/5] create document"
DOC_JSON="$(curl -fsS -X POST "$BASE_URL/api/documents" \
  -H 'Content-Type: application/json' \
  -d '{"original_filename":"ap1-smoke.pdf","notes":"smoke"}')"
DOC_ID="$(printf '%s' "$DOC_JSON" | extract_json_field 'id')"
echo "document_id=$DOC_ID"

echo "[2/5] create tag"
TAG_JSON="$(curl -fsS -X POST "$BASE_URL/api/tags" \
  -H 'Content-Type: application/json' \
  -d '{"name":"smoke-tag"}')"
TAG_ID="$(printf '%s' "$TAG_JSON" | extract_json_field 'id')"
echo "tag_id=$TAG_ID"

echo "[3/5] replace document tags"
REPLACE_JSON="$(curl -fsS -X POST "$BASE_URL/api/documents/$DOC_ID/tags" \
  -H 'Content-Type: application/json' \
  -d "{\"tag_ids\":[\"$TAG_ID\"]}")"
printf '%s\n' "$REPLACE_JSON" > /dev/null

echo "[4/5] filter documents by tag"
curl -fsS "$BASE_URL/api/documents?tag=$TAG_ID&limit=10&offset=0" > /dev/null

echo "[5/5] list tags with usage_count"
curl -fsS "$BASE_URL/api/tags?include_count=true" > /dev/null

echo "AP1 smoke test passed"
