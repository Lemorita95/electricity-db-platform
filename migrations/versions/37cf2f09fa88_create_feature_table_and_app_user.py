"""initial schema

Revision ID: 37cf2f09fa88
Revises: 
Create Date: 2026-06-07 14:20:20.781530

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import os

revision: str = '37cf2f09fa88'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'price',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zone', sa.String(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('resolution', sa.String(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zone', 'timestamp', name='uq_price_zone_timestamp')
    )
    op.create_table(
        'demand',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zone', sa.String(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('resolution', sa.String(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zone', 'timestamp', name='uq_demand_zone_timestamp')
    )
    op.create_table(
        'weather',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zone', sa.String(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('resolution', sa.String(), nullable=False),
        sa.Column('fdir', sa.Float(), nullable=True),
        sa.Column('ssrd', sa.Float(), nullable=True),
        sa.Column('temperature_2m', sa.Float(), nullable=True),
        sa.Column('wind_u_10m', sa.Float(), nullable=True),
        sa.Column('wind_v_10m', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zone', 'timestamp', name='uq_weather_zone_timestamp')
    )

    manager_user = os.environ["MANAGER_USER"]
    manager_password = os.environ["MANAGER_PASSWORD"]
    readonly_user = os.environ["READONLY_USER"]
    readonly_password = os.environ["READONLY_PASSWORD"]
    db_name = os.environ["POSTGRES_DB"]

    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{manager_user}') THEN
                CREATE USER {manager_user} WITH PASSWORD '{manager_password}';
                GRANT CONNECT ON DATABASE {db_name} TO {manager_user};
                GRANT USAGE, CREATE ON SCHEMA public TO {manager_user};
                GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO {manager_user};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {manager_user};
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO {manager_user};
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {manager_user};
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{readonly_user}') THEN
                CREATE USER {readonly_user} WITH PASSWORD '{readonly_password}';
                GRANT CONNECT ON DATABASE {db_name} TO {readonly_user};
                GRANT USAGE ON SCHEMA public TO {readonly_user};
                GRANT SELECT ON ALL TABLES IN SCHEMA public TO {readonly_user};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {readonly_user};
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {readonly_user};
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {readonly_user};
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.drop_table('weather')
    op.drop_table('demand')
    op.drop_table('price')