"""오개념(misconceptions) 테이블, 서술형 채점 결과 칸, 응시의 서술형 채점 상태·요약

Revision ID: d1a9c3e7f5b2
Revises: c7e3f5a9d2b1
Create Date: 2026-11-17
"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "d1a9c3e7f5b2"
down_revision = "c7e3f5a9d2b1"
branch_labels = None
depends_on = None

S = sqlmodel.sql.sqltypes.AutoString


def upgrade() -> None:
    op.create_table(
        "misconceptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("problem_id", sa.Integer(), sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("wrong_choice_index", sa.Integer(), nullable=False),
        sa.Column("label", S(length=100), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("evidence_found", sa.Boolean(), nullable=False),
        sa.Column("source_material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("status", S(length=20), nullable=False),
        sa.Column("model", S(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("problem_id", "wrong_choice_index"),
    )
    op.create_index("ix_misconceptions_problem_id", "misconceptions", ["problem_id"])
    with op.batch_alter_table("paper_essay_images") as b:
        b.add_column(sa.Column("score", sa.Integer(), nullable=True))
        b.add_column(sa.Column("transcription", sa.Text(), nullable=True))
        b.add_column(sa.Column("feedback", sa.Text(), nullable=True))
        b.add_column(sa.Column("rubric_detail", sa.JSON(), nullable=True))
        b.add_column(sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("paper_takes") as b:
        b.add_column(sa.Column("essay_status", S(length=20), nullable=False, server_default="none"))
        b.add_column(sa.Column("summary", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("paper_takes") as b:
        b.drop_column("summary")
        b.drop_column("essay_status")
    with op.batch_alter_table("paper_essay_images") as b:
        b.drop_column("graded_at")
        b.drop_column("rubric_detail")
        b.drop_column("feedback")
        b.drop_column("transcription")
        b.drop_column("score")
    op.drop_index("ix_misconceptions_problem_id", "misconceptions")
    op.drop_table("misconceptions")
