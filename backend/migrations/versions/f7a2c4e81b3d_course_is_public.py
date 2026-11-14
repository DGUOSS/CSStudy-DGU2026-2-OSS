"""공용 강좌: courses.is_public (수강 기록 없이 누구나 들어가는 강좌)

Revision ID: f7a2c4e81b3d
Revises: e3f1a9c7b2d4
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "f7a2c4e81b3d"
down_revision = "e3f1a9c7b2d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("courses") as b:
        b.add_column(
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("courses") as b:
        b.drop_column("is_public")
