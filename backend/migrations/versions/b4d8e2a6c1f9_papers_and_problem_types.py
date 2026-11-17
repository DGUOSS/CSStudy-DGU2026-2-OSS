"""종이 시험: papers·paper_takes·paper_essay_images, problems에 유형(qtype)·모범답안·배점표·배점

Revision ID: b4d8e2a6c1f9
Revises: f7a2c4e81b3d
Create Date: 2026-11-13
"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "b4d8e2a6c1f9"
down_revision = "f7a2c4e81b3d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("problems") as b:
        b.add_column(sa.Column("qtype", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False, server_default="mcq"))
        b.add_column(sa.Column("model_answer", sa.Text(), nullable=True))
        b.add_column(sa.Column("rubric", sa.JSON(), nullable=True))
        b.add_column(sa.Column("points", sa.Integer(), nullable=False, server_default="1"))

    op.create_table(
        "papers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("problem_ids", sa.JSON(), nullable=False),
        sa.Column("time_limit_min", sa.Integer(), nullable=False),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_papers_course_id", "papers", ["course_id"])

    op.create_table(
        "paper_takes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_sec", sa.Integer(), nullable=True),
        sa.Column("late", sa.Boolean(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=True),
        sa.Column("mcq_score", sa.Integer(), nullable=True),
        sa.Column("essay_score", sa.Integer(), nullable=True),
        sa.Column("total_points", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
    )
    op.create_index("ix_paper_takes_paper_id", "paper_takes", ["paper_id"])
    op.create_index("ix_paper_takes_user_id", "paper_takes", ["user_id"])

    op.create_table(
        "paper_essay_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("take_id", sa.Integer(), sa.ForeignKey("paper_takes.id"), nullable=False),
        sa.Column("problem_id", sa.Integer(), sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("image", sa.LargeBinary(), nullable=False),
    )
    op.create_index("ix_paper_essay_images_take_id", "paper_essay_images", ["take_id"])


def downgrade() -> None:
    op.drop_index("ix_paper_essay_images_take_id", "paper_essay_images")
    op.drop_table("paper_essay_images")
    op.drop_index("ix_paper_takes_user_id", "paper_takes")
    op.drop_index("ix_paper_takes_paper_id", "paper_takes")
    op.drop_table("paper_takes")
    op.drop_index("ix_papers_course_id", "papers")
    op.drop_table("papers")
    with op.batch_alter_table("problems") as b:
        b.drop_column("points")
        b.drop_column("rubric")
        b.drop_column("model_answer")
        b.drop_column("qtype")
