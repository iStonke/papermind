"""shared scanner inbox by default.

Revision ID: 079_shared_scanner_inbox
Revises: 078_scanner_discovery
Create Date: 2026-08-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "079_shared_scanner_inbox"
down_revision: Union[str, None] = "078_scanner_discovery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def _replace_policy(*, shared_without_recipients: bool) -> None:
    if shared_without_recipients:
        access_clause = f"""
            AND {_OWNER_EXPR} IS NOT NULL
            AND (
                NOT EXISTS (
                    SELECT 1
                    FROM scanner_device_recipients any_recipient
                    WHERE any_recipient.scanner_device_id = d.id
                )
                OR EXISTS (
                    SELECT 1
                    FROM scanner_device_recipients own_recipient
                    WHERE own_recipient.scanner_device_id = d.id
                      AND own_recipient.user_id = {_OWNER_EXPR}
                )
            )
        """
        configured_clause = "AND d.configured = true"
    else:
        access_clause = f"""
            AND EXISTS (
                SELECT 1
                FROM scanner_device_recipients own_recipient
                WHERE own_recipient.scanner_device_id = d.id
                  AND own_recipient.user_id = {_OWNER_EXPR}
            )
        """
        configured_clause = ""

    scanner_item_clause = f"""
        owner_id IS NULL
        AND source_type = 'scanner'
        AND claimed_at IS NULL
        AND scanner_device_id IS NOT NULL
        AND EXISTS (
            SELECT 1
            FROM scanner_devices d
            WHERE d.id = import_inbox_items.scanner_device_id
              AND d.enabled = true
              {configured_clause}
              {access_clause}
        )
    """

    op.execute("DROP POLICY IF EXISTS import_inbox_items_owner_isolation ON import_inbox_items")
    op.execute(
        f"""
        CREATE POLICY import_inbox_items_owner_isolation ON import_inbox_items
        USING (
            owner_id = {_OWNER_EXPR}
            OR ({scanner_item_clause})
        )
        WITH CHECK (
            owner_id = {_OWNER_EXPR}
            OR ({scanner_item_clause})
        )
        """
    )


def upgrade() -> None:
    _replace_policy(shared_without_recipients=True)


def downgrade() -> None:
    _replace_policy(shared_without_recipients=False)
