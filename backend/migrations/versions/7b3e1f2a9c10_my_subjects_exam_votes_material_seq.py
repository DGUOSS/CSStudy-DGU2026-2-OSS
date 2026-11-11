"""my subjects, exam votes and selections, material seq naming

Revision ID: 7b3e1f2a9c10
Revises: 562de94c5934
Create Date: 2026-11-11 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = '7b3e1f2a9c10'
down_revision: Union[str, Sequence[str], None] = '562de94c5934'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KIND_LABEL = {"lecture": "교안", "exam": "족보", "note": "시험정보"}


def upgrade() -> None:
    op.create_table(
        'user_subjects',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('semester', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
        sa.Column('source', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'subject_id'),
    )
    op.create_index(op.f('ix_user_subjects_subject_id'), 'user_subjects', ['subject_id'])
    op.create_table(
        'material_votes',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'material_id'),
    )
    op.create_index(op.f('ix_material_votes_material_id'), 'material_votes', ['material_id'])
    op.create_table(
        'exam_selections',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id']),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'material_id'),
    )
    op.create_index(op.f('ix_exam_selections_course_id'), 'exam_selections', ['course_id'])
    op.add_column('materials', sa.Column('seq', sa.Integer(), nullable=True))

    # 기존 자료에 번호와 '과목명 종류 번호' 제목을 붙인다. 새 판은 대체한 옛 판의 번호를 이어받는다.
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT m.id, m.course_id, m.kind, m.replaced_by, s.name FROM materials m "
        "JOIN courses c ON c.id = m.course_id JOIN subjects s ON s.id = c.subject_id "
        "ORDER BY m.created_at, m.id"
    )).fetchall()
    seq_of: dict[int, int] = {}
    counter: dict[tuple[int, str], int] = {}
    preds: dict[int, list[int]] = {}
    for mid, _c, _k, replaced_by, _s in rows:
        if replaced_by is not None:
            preds.setdefault(replaced_by, []).append(mid)
    for mid, course_id, kind, _r, subject_name in rows:
        inherited = [seq_of[p] for p in preds.get(mid, []) if p in seq_of]
        if inherited:
            seq = min(inherited)
        else:
            key = (course_id, kind)
            counter[key] = counter.get(key, 0) + 1
            seq = counter[key]
        seq_of[mid] = seq
        title = f"{subject_name} {KIND_LABEL.get(kind, '자료')} {seq}"
        bind.execute(
            sa.text("UPDATE materials SET seq = :seq, title = :title WHERE id = :id"),
            {"seq": seq, "title": title, "id": mid},
        )


def downgrade() -> None:
    op.drop_column('materials', 'seq')
    op.drop_index(op.f('ix_exam_selections_course_id'), table_name='exam_selections')
    op.drop_table('exam_selections')
    op.drop_index(op.f('ix_material_votes_material_id'), table_name='material_votes')
    op.drop_table('material_votes')
    op.drop_index(op.f('ix_user_subjects_subject_id'), table_name='user_subjects')
    op.drop_table('user_subjects')
