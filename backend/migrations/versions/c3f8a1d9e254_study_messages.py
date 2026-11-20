"""스터디 공간 채팅

Revision ID: c3f8a1d9e254
Revises: e766111f9118
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op

revision = "c3f8a1d9e254"
down_revision = "e766111f9118"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("study_groups.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_study_messages_group_id", "study_messages", ["group_id"])
    op.create_index("ix_study_messages_user_id", "study_messages", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_study_messages_user_id", "study_messages")
    op.drop_index("ix_study_messages_group_id", "study_messages")
    op.drop_table("study_messages")
