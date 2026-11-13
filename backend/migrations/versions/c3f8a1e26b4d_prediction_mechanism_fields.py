"""prediction mechanism fields

Adds crowding, mechanism_id and role to impact_predictions. All three are
nullable: rule-engine predictions and rows written before this migration
leave them empty.

Revision ID: c3f8a1e26b4d
Revises: 49c9540f91c7
Create Date: 2026-11-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f8a1e26b4d'
down_revision: Union[str, Sequence[str], None] = '49c9540f91c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'impact_predictions',
        sa.Column('crowding', sa.String(length=8), nullable=True),
    )
    op.add_column(
        'impact_predictions',
        sa.Column('mechanism_id', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'impact_predictions',
        sa.Column('role', sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('impact_predictions', 'role')
    op.drop_column('impact_predictions', 'mechanism_id')
    op.drop_column('impact_predictions', 'crowding')
