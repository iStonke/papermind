"""make wiki evidence immutable and cryptographically self-consistent.

Revision ID: 073_wiki_evidence_immutability
Revises: 072_wiki_evidence_integrity
Create Date: 2026-08-12 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "073_wiki_evidence_immutability"
down_revision: Union[str, None] = "072_wiki_evidence_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TRIGGER wiki_claim_evidence_validate_source ON wiki_claim_evidence")
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION validate_wiki_evidence_source()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            source_row record;
        BEGIN
            SELECT d.owner_id AS document_owner_id, d.is_deleted, d.text_hash,
                   c.doc_id, c.text AS chunk_text, c.content_hash,
                   wc.owner_id AS claim_owner_id
            INTO source_row
            FROM documents d
            JOIN doc_chunks c ON c.id = NEW.chunk_id
            JOIN wiki_claims wc ON wc.id = NEW.claim_id
            WHERE d.id = NEW.document_id;

            IF NOT FOUND
               OR source_row.doc_id <> NEW.document_id
               OR source_row.document_owner_id <> NEW.owner_id
               OR source_row.claim_owner_id <> NEW.owner_id
               OR source_row.is_deleted
               OR source_row.content_hash <> NEW.chunk_content_hash
               OR (NEW.document_text_hash IS NOT NULL AND source_row.text_hash IS DISTINCT FROM NEW.document_text_hash)
               OR NEW.quote_hash <> encode(sha256(convert_to(NEW.quote, 'UTF8')), 'hex')
               OR length(btrim(NEW.quote)) = 0
               OR position(
                    lower(regexp_replace(NEW.quote, '\s+', ' ', 'g'))
                    IN lower(regexp_replace(source_row.chunk_text, '\s+', ' ', 'g'))
                  ) = 0
            THEN
                RAISE EXCEPTION 'wiki evidence must match a current owner-scoped source chunk and quote hash'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER wiki_claim_evidence_validate_source "
        "BEFORE INSERT ON wiki_claim_evidence "
        "FOR EACH ROW EXECUTE FUNCTION validate_wiki_evidence_source()"
    )
    op.execute(
        """
        CREATE FUNCTION prevent_wiki_evidence_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'wiki evidence is immutable; create a correcting claim instead';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER wiki_claim_evidence_immutable "
        "BEFORE UPDATE ON wiki_claim_evidence "
        "FOR EACH ROW EXECUTE FUNCTION prevent_wiki_evidence_update()"
    )

    # If a source is removed, another merely present support row is not enough:
    # the remaining row must still resolve to a current, exact source excerpt.
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION stale_wiki_claim_on_evidence_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.support_role = 'supports' AND NOT EXISTS (
                SELECT 1
                FROM wiki_claim_evidence e
                JOIN documents d ON d.id = e.document_id
                JOIN doc_chunks c ON c.id = e.chunk_id AND c.doc_id = d.id
                WHERE e.claim_id = OLD.claim_id
                  AND e.id <> OLD.id
                  AND e.owner_id = OLD.owner_id
                  AND e.support_role = 'supports'
                  AND d.owner_id = OLD.owner_id
                  AND d.is_deleted = false
                  AND e.chunk_content_hash = c.content_hash
                  AND (e.document_text_hash IS NULL OR e.document_text_hash = d.text_hash)
                  AND e.quote_hash = encode(sha256(convert_to(e.quote, 'UTF8')), 'hex')
                  AND position(
                        lower(regexp_replace(e.quote, '\s+', ' ', 'g'))
                        IN lower(regexp_replace(c.text, '\s+', ' ', 'g'))
                      ) > 0
            ) THEN
                UPDATE wiki_claims
                SET status = CASE WHEN status = 'active' THEN 'stale' ELSE status END,
                    updated_at = now()
                WHERE id = OLD.claim_id;
            END IF;
            RETURN OLD;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER wiki_claim_evidence_immutable ON wiki_claim_evidence")
    op.execute("DROP FUNCTION prevent_wiki_evidence_update()")
    op.execute("DROP TRIGGER wiki_claim_evidence_validate_source ON wiki_claim_evidence")
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION validate_wiki_evidence_source()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            source_row record;
        BEGIN
            SELECT d.owner_id AS document_owner_id, d.is_deleted, d.text_hash,
                   c.doc_id, c.text AS chunk_text, c.content_hash
            INTO source_row
            FROM documents d
            JOIN doc_chunks c ON c.id = NEW.chunk_id
            WHERE d.id = NEW.document_id;

            IF NOT FOUND
               OR source_row.doc_id <> NEW.document_id
               OR source_row.document_owner_id <> NEW.owner_id
               OR source_row.is_deleted
               OR source_row.content_hash <> NEW.chunk_content_hash
               OR (NEW.document_text_hash IS NOT NULL AND source_row.text_hash IS DISTINCT FROM NEW.document_text_hash)
               OR length(btrim(NEW.quote)) = 0
               OR position(
                    lower(regexp_replace(NEW.quote, '\s+', ' ', 'g'))
                    IN lower(regexp_replace(source_row.chunk_text, '\s+', ' ', 'g'))
                  ) = 0
            THEN
                RAISE EXCEPTION 'wiki evidence must match a current owner-scoped source chunk'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER wiki_claim_evidence_validate_source "
        "BEFORE INSERT OR UPDATE ON wiki_claim_evidence "
        "FOR EACH ROW EXECUTE FUNCTION validate_wiki_evidence_source()"
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION stale_wiki_claim_on_evidence_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.support_role = 'supports' AND NOT EXISTS (
                SELECT 1 FROM wiki_claim_evidence e
                WHERE e.claim_id = OLD.claim_id AND e.id <> OLD.id AND e.support_role = 'supports'
            ) THEN
                UPDATE wiki_claims
                SET status = CASE WHEN status = 'active' THEN 'stale' ELSE status END,
                    updated_at = now()
                WHERE id = OLD.claim_id;
            END IF;
            RETURN OLD;
        END;
        $$
        """
    )
