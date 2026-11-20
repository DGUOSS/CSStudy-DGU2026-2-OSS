"""팀 프로젝트 라벨: 강의계획서 판정(catalog_offerings) + 후기 응답(course_reviews)

Revision ID: a4d2e8f61c07
Revises: e766111f9118
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op

revision = "a4d2e8f61c07"
down_revision = "e766111f9118"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("catalog_offerings") as b:
        b.add_column(sa.Column("team_project", sa.String(length=20), nullable=True))
        b.add_column(sa.Column("team_evidence", sa.String(length=300), nullable=True))
        b.add_column(sa.Column("syllabus_checked_at", sa.DateTime(), nullable=True))
    with op.batch_alter_table("course_reviews") as b:
        b.add_column(sa.Column("team_project", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("course_reviews") as b:
        b.drop_column("team_project")
    with op.batch_alter_table("catalog_offerings") as b:
        b.drop_column("syllabus_checked_at")
        b.drop_column("team_evidence")
        b.drop_column("team_project")
