"""Recompute note body_text without image file names.

Bilder trugen ihren Dateinamen (alt/title, z. B. „image.png") in den
abgeleiteten Notiztext und damit in Listenvorschau und Suche. Die Ableitung
berücksichtigt jetzt nur noch die Bildunterschrift; bestehende Notizen mit
Bildern werden hier einmalig neu berechnet. updated_at bleibt unverändert,
der Suchindex folgt über den bestehenden Trigger.
"""
import json
import re

from alembic import op
import sqlalchemy as sa

revision = '110_note_text_no_image_names'
down_revision = '109_note_generated_title'
branch_labels = None
depends_on = None

# Stand der Ableitung zum Zeitpunkt dieser Migration (app/services/note_service.py).
_NODE_TEXT_ATTRS = {
    "documentChip": ("title",),
    "wikiLink": ("label",),
    "ocrQuote": ("text",),
    "aiBlock": ("text",),
    "image": ("caption",),
}
_WS = re.compile(r"\s+")


def _text(node):
    if not isinstance(node, dict):
        return ""
    parts = []
    if node.get("text"):
        parts.append(str(node["text"]))
    attrs = node.get("attrs") or {}
    for key in _NODE_TEXT_ATTRS.get(node.get("type", ""), ()):
        value = attrs.get(key)
        if value:
            parts.append(str(value))
    for child in node.get("content") or []:
        child_text = _text(child)
        if child_text:
            parts.append(child_text)
    return " ".join(parts)


def upgrade():
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, body_json, body_text FROM note "
        "WHERE body_json::text LIKE '%\"image\"%'"
    )).fetchall()
    for note_id, body_json, body_text in rows:
        body = body_json if isinstance(body_json, dict) else json.loads(body_json or "null")
        text = _WS.sub(" ", _text(body)).strip()
        if text != (body_text or ""):
            bind.execute(
                sa.text("UPDATE note SET body_text = :text WHERE id = :id"),
                {"text": text, "id": note_id},
            )


def downgrade():
    # Rein abgeleitete Daten; beim nächsten Speichern ohnehin neu berechnet.
    pass
