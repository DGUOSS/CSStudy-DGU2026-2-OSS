"""수강 강좌(과목·교수)당 한 번 작성하는 강좌 후기."""
import sqlalchemy as sa
from alembic import op

revision = "a4c9e2b710df"
down_revision = "f7a2c4e81b3d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("course_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("recommendation", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id"), nullable=False),
        sa.Column("year", sa.String(4), nullable=False),
        sa.Column("sem_cd", sa.String(20), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("workload", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "course_id"),
    )
    op.create_index("ix_course_reviews_user_id", "course_reviews", ["user_id"])
    op.create_index("ix_course_reviews_course_id", "course_reviews", ["course_id"])


def downgrade():
    op.drop_table("course_reviews")
