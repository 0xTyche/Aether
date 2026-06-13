"""events analysis jsonb

Revision ID: 49c9540f91c7
Revises: a520060dd1d5
Create Date: 2026-06-13 19:54:34.275490

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '49c9540f91c7'
down_revision: Union[str, Sequence[str], None] = 'a520060dd1d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'events',
        sa.Column('analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # NOTE: autogenerate proposed dropping `prices_ts_idx`, but TimescaleDB
    # creates and owns that index as part of create_hypertable(). Dropping it
    # would break the hypertable. Leave it alone.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('events', 'analysis')
