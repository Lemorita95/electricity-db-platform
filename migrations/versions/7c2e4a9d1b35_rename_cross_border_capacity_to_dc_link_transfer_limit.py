"""rename cross_border_capacity to dc_link_transfer_limit

Revision ID: 7c2e4a9d1b35
Revises: 5e1b7c9a2d40
Create Date: 2026-11-08 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c2e4a9d1b35'
down_revision: Union[str, Sequence[str], None] = '5e1b7c9a2d40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rename(old: str, new: str) -> None:
    # the primary key and id sequence carry Postgres' default names, derived from the table name
    op.rename_table(old, new)
    op.execute(f'ALTER TABLE {new} RENAME CONSTRAINT uq_{old}_zone_timestamp TO uq_{new}_zone_timestamp')
    op.execute(f'ALTER TABLE {new} RENAME CONSTRAINT {old}_pkey TO {new}_pkey')
    op.execute(f'ALTER SEQUENCE {old}_id_seq RENAME TO {new}_id_seq')


def upgrade() -> None:
    """Upgrade schema."""
    _rename('cross_border_capacity', 'dc_link_transfer_limit')


def downgrade() -> None:
    """Downgrade schema."""
    _rename('dc_link_transfer_limit', 'cross_border_capacity')
