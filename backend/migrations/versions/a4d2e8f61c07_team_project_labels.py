"""팀 프로젝트 라벨: 강의계획서 판정(catalog_offerings) + 후기 응답(course_reviews)

Revision ID: a4d2e8f61c07
Revises: c3f8a1d9e254
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op

revision = "a4d2e8f61c07"
down_revision = "c3f8a1d9e254"  # 채팅(#27) 다음으로 이음
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("catalog_offerings") as b:
        b.add_column(sa.Column("team_project", sa.String(length=20), nullable=True))
        b.add_column(sa.Column("team_evidence", sa.String(length=300), nullable=True))
        b.add_column(sa.Column("syllabus_checked_at", sa.DateTime(), nullable=True))
    with op.batch_alter_table("course_reviews") as b:
        b.add_column(sa.Column("team_project", sa.Boolean(), nullable=True))
    op.create_table(
        "team_project_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("year", sa.String(length=4), nullable=False),
        sa.Column("sem_cd", sa.String(length=20), nullable=False),
        sa.Column("team_project", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "course_id", "year", "sem_cd"),
    )
    op.create_index("ix_team_project_reports_user_id", "team_project_reports", ["user_id"])
    op.create_index("ix_team_project_reports_course_id", "team_project_reports", ["course_id"])
    op.create_table(
        "team_project_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("year", sa.String(length=4), nullable=False),
        sa.Column("sem_cd", sa.String(length=20), nullable=False),
        sa.Column("team_project", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=False),
        sa.Column("set_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("course_id", "year", "sem_cd"),
    )
    op.create_index("ix_team_project_overrides_course_id", "team_project_overrides", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_team_project_overrides_course_id", "team_project_overrides")
    op.drop_table("team_project_overrides")
    op.drop_index("ix_team_project_reports_course_id", "team_project_reports")
    op.drop_index("ix_team_project_reports_user_id", "team_project_reports")
    op.drop_table("team_project_reports")
    with op.batch_alter_table("course_reviews") as b:
        b.drop_column("team_project")
    with op.batch_alter_table("catalog_offerings") as b:
        b.drop_column("syllabus_checked_at")
        b.drop_column("team_evidence")
        b.drop_column("team_project")
