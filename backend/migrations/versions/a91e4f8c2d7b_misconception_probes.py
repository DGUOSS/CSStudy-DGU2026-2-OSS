"""Store misconception hypotheses and confirmation problems.

Revision ID: a91e4f8c2d7b
Revises: bc3bb4c8a5a3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "a91e4f8c2d7b"
down_revision: Union[str, Sequence[str], None] = "bc3bb4c8a5a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "misconception_probes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("wrong_choice_index", sa.Integer(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("choices", sa.JSON(), nullable=False),
        sa.Column("answer_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("source_material_id", sa.Integer(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"]),
        sa.ForeignKeyConstraint(["source_material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("problem_id", "wrong_choice_index"),
    )
    op.create_index(
        op.f("ix_misconception_probes_problem_id"), "misconception_probes", ["problem_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_misconception_probes_problem_id"), table_name="misconception_probes")
    op.drop_table("misconception_probes")
