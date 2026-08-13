"""enforce current source hashes and exact quotes for wiki evidence.

Revision ID: 072_wiki_evidence_integrity
Revises: 071_llm_wiki_trust_foundation
Create Date: 2026-08-12 00:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "072_wiki_evidence_integrity"
down_revision: Union[str, None] = "071_llm_wiki_trust_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE FUNCTION validate_wiki_evidence_source()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            source_row record;
        BEGIN
            SELECT d.owner_id AS document_owner_id, d.is_deleted, d.text_hash,
                   c.doc_id, c.text AS chunk_text,
                   c.content_hash
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

    # The original deferred invariant required an evidence row. Replace it with
    # the stronger invariant that the row still matches the current document
    # and chunk hashes at commit time.
    op.execute("DROP TRIGGER wiki_claims_require_evidence ON wiki_claims")
    op.execute("DROP FUNCTION enforce_active_wiki_fact_evidence()")
    op.execute(
        r"""
        CREATE FUNCTION enforce_active_wiki_fact_evidence()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.claim_type = 'fact' AND NEW.status = 'active' AND NOT EXISTS (
                SELECT 1
                FROM wiki_claim_evidence e
                JOIN documents d ON d.id = e.document_id
                JOIN doc_chunks c ON c.id = e.chunk_id AND c.doc_id = d.id
                WHERE e.claim_id = NEW.id
                  AND e.owner_id = NEW.owner_id
                  AND d.owner_id = NEW.owner_id
                  AND e.support_role = 'supports'
                  AND d.is_deleted = false
                  AND e.chunk_content_hash = c.content_hash
                  AND (e.document_text_hash IS NULL OR e.document_text_hash = d.text_hash)
                  AND position(
                        lower(regexp_replace(e.quote, '\s+', ' ', 'g'))
                        IN lower(regexp_replace(c.text, '\s+', ' ', 'g'))
                      ) > 0
            ) THEN
                RAISE EXCEPTION 'active wiki fact requires current supporting source evidence'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER wiki_claims_require_evidence "
        "AFTER INSERT OR UPDATE OF status, claim_type ON wiki_claims "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION enforce_active_wiki_fact_evidence()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER wiki_claims_require_evidence ON wiki_claims")
    op.execute("DROP FUNCTION enforce_active_wiki_fact_evidence()")
    op.execute(
        """
        CREATE FUNCTION enforce_active_wiki_fact_evidence()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.claim_type = 'fact' AND NEW.status = 'active' AND NOT EXISTS (
                SELECT 1 FROM wiki_claim_evidence e
                WHERE e.claim_id = NEW.id AND e.owner_id = NEW.owner_id AND e.support_role = 'supports'
            ) THEN
                RAISE EXCEPTION 'active wiki fact requires supporting source evidence'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER wiki_claims_require_evidence "
        "AFTER INSERT OR UPDATE OF status, claim_type ON wiki_claims "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION enforce_active_wiki_fact_evidence()"
    )
    op.execute("DROP TRIGGER wiki_claim_evidence_validate_source ON wiki_claim_evidence")
    op.execute("DROP FUNCTION validate_wiki_evidence_source()")
