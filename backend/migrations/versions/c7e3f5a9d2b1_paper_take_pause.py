"""종이 시험 타이머 일시정지: paper_takes.paused_at·paused_sec·pause_count

Revision ID: c7e3f5a9d2b1
Revises: b4d8e2a6c1f9
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "c7e3f5a9d2b1"
down_revision = "b4d8e2a6c1f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("paper_takes") as b:
        b.add_column(sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("paused_sec", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("pause_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("paper_takes") as b:
        b.drop_column("pause_count")
        b.drop_column("paused_sec")
        b.drop_column("paused_at")
