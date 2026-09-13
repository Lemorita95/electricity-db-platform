"""add production resources and generating units

Revision ID: 3bfefce53d2c
Revises: 37cf2f09fa88
Create Date: 2026-08-28 13:13:42.302321

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3bfefce53d2c'
down_revision: Union[str, Sequence[str], None] = '37cf2f09fa88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('production_resource',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resource_mrid', sa.String(), nullable=False),
    sa.Column('resource_name', sa.String(), nullable=False),
    sa.Column('location_name', sa.String(), nullable=True),
    sa.Column('zone', sa.String(), nullable=False),
    sa.Column('control_area_mrid', sa.String(), nullable=True),
    sa.Column('provider_mrid', sa.String(), nullable=True),
    sa.Column('business_type', sa.String(), nullable=False),
    sa.Column('psr_type', sa.String(), nullable=False),
    sa.Column('high_voltage_limit_kv', sa.Float(), nullable=True),
    sa.Column('nominal_p_mw', sa.Float(), nullable=True),
    sa.Column('implementation_date', sa.Date(), nullable=False),
    sa.Column('source_ts_mrid', sa.String(), nullable=False),
    sa.Column('fetched_at', sa.TIMESTAMP(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('resource_mrid', 'implementation_date', name='uq_resource_mrid_impl_date')
    )
    op.create_index(op.f('ix_production_resource_resource_mrid'), 'production_resource', ['resource_mrid'], unique=False)
    op.create_index(op.f('ix_production_resource_zone'), 'production_resource', ['zone'], unique=False)
    op.create_table('generating_unit',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resource_id', sa.Integer(), nullable=False),
    sa.Column('unit_mrid', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('nominal_p_mw', sa.Float(), nullable=False),
    sa.Column('psr_type', sa.String(), nullable=False),
    sa.Column('location_name', sa.String(), nullable=True),
    sa.Column('implementation_date', sa.Date(), nullable=False),
    sa.Column('fetched_at', sa.TIMESTAMP(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['resource_id'], ['production_resource.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('unit_mrid', 'implementation_date', name='uq_unit_mrid_impl_date')
    )
    op.create_index(op.f('ix_generating_unit_resource_id'), 'generating_unit', ['resource_id'], unique=False)
    op.create_index(op.f('ix_generating_unit_unit_mrid'), 'generating_unit', ['unit_mrid'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_generating_unit_unit_mrid'), table_name='generating_unit')
    op.drop_index(op.f('ix_generating_unit_resource_id'), table_name='generating_unit')
    op.drop_table('generating_unit')
    op.drop_index(op.f('ix_production_resource_zone'), table_name='production_resource')
    op.drop_index(op.f('ix_production_resource_resource_mrid'), table_name='production_resource')
    op.drop_table('production_resource')
