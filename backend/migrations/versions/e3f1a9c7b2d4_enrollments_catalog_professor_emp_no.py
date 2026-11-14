"""enrollments(ndrims records), catalog offerings, professor emp_no, keyed course requests

엔드림스 수강 기록으로 들어갈 강좌를 정한다(docs/NDRIMS.md). 직접 고르던 '내 과목'(user_subjects)은
없앤다. 학생은 수강 기록을 다시 가져와야 한다.

Revision ID: e3f1a9c7b2d4
Revises: bc3bb4c8a5a3
Create Date: 2026-11-12 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'e3f1a9c7b2d4'
down_revision: Union[str, Sequence[str], None] = 'bc3bb4c8a5a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = sqlmodel.sql.sqltypes.AutoString


def upgrade() -> None:
    op.create_table(
        'enrollments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('year', S(length=4), nullable=False),
        sa.Column('sem_cd', S(length=20), nullable=False),
        sa.Column('sbj_no', S(length=20), nullable=False),
        sa.Column('sbj_nm', S(length=200), nullable=False),
        sa.Column('dvcls', S(length=10), nullable=False),
        sa.Column('emp_nm', S(length=50), nullable=True),
        sa.Column('emp_no', S(length=20), nullable=True),
        sa.Column('course_id', sa.Integer(), nullable=True),
        sa.Column('source', S(length=20), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'year', 'sem_cd', 'sbj_no', 'dvcls'),
    )
    op.create_index(op.f('ix_enrollments_user_id'), 'enrollments', ['user_id'])
    op.create_index(op.f('ix_enrollments_sbj_no'), 'enrollments', ['sbj_no'])
    op.create_index(op.f('ix_enrollments_course_id'), 'enrollments', ['course_id'])

    op.create_table(
        'catalog_offerings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', S(length=4), nullable=False),
        sa.Column('sem_cd', S(length=20), nullable=False),
        sa.Column('sbj_no', S(length=20), nullable=False),
        sa.Column('sbj_nm', S(length=200), nullable=False),
        sa.Column('dvcls', S(length=10), nullable=False),
        sa.Column('emp_no', S(length=20), nullable=True),
        sa.Column('emp_nm', S(length=50), nullable=True),
        sa.Column('colg_nm', S(length=100), nullable=True),
        sa.Column('dpt_nm', S(length=100), nullable=True),
        sa.Column('cpdiv_nm', S(length=50), nullable=True),
        sa.Column('cdt', S(length=10), nullable=True),
        sa.Column('timetable', S(length=300), nullable=True),
        sa.Column('room', S(length=300), nullable=True),
        sa.Column('mid_rate', sa.Integer(), nullable=True),
        sa.Column('fnl_rate', sa.Integer(), nullable=True),
        sa.Column('atnd_rate', sa.Integer(), nullable=True),
        sa.Column('proj_rate', sa.Integer(), nullable=True),
        sa.Column('plan_url', S(length=500), nullable=True),
        sa.Column('imported_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year', 'sem_cd', 'sbj_no', 'dvcls'),
    )
    for col in ('year', 'sem_cd', 'sbj_no'):
        op.create_index(op.f(f'ix_catalog_offerings_{col}'), 'catalog_offerings', [col])

    with op.batch_alter_table('professors') as b:
        b.add_column(sa.Column('emp_no', S(length=20), nullable=True))
        b.create_index(b.f('ix_professors_emp_no'), ['emp_no'], unique=True)

    with op.batch_alter_table('course_requests') as b:
        b.add_column(sa.Column('source', S(length=20), nullable=False, server_default='manual'))
        b.add_column(sa.Column('professor_emp_no', S(length=20), nullable=True))

    op.drop_index(op.f('ix_user_subjects_subject_id'), table_name='user_subjects')
    op.drop_table('user_subjects')


def downgrade() -> None:
    op.create_table(
        'user_subjects',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('status', S(length=20), nullable=False),
        sa.Column('semester', S(length=20), nullable=True),
        sa.Column('source', S(length=20), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'subject_id'),
    )
    op.create_index(op.f('ix_user_subjects_subject_id'), 'user_subjects', ['subject_id'])
    with op.batch_alter_table('course_requests') as b:
        b.drop_column('professor_emp_no')
        b.drop_column('source')
    with op.batch_alter_table('professors') as b:
        b.drop_index(b.f('ix_professors_emp_no'))
        b.drop_column('emp_no')
    for col in ('year', 'sem_cd', 'sbj_no'):
        op.drop_index(op.f(f'ix_catalog_offerings_{col}'), table_name='catalog_offerings')
    op.drop_table('catalog_offerings')
    for col in ('user_id', 'sbj_no', 'course_id'):
        op.drop_index(op.f(f'ix_enrollments_{col}'), table_name='enrollments')
    op.drop_table('enrollments')
