"""두 갈래 합치기: 강좌 후기(a4c9e2b710df, 배포 DB에 먼저 적용됨)와 종이 시험·오개념(d1a9c3e7f5b2)

둘 다 f7a2c4e81b3d에서 갈라졌다. 표는 서로 겹치지 않아 합치기만 한다.

Revision ID: e5b7d9f1a3c2
Revises: d1a9c3e7f5b2, a4c9e2b710df
Create Date: 2026-11-17
"""

revision = "e5b7d9f1a3c2"
down_revision = ("d1a9c3e7f5b2", "a4c9e2b710df")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
