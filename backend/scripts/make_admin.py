"""가입한 계정을 관리자로 지정(또는 해제)한다. backend/.env의 DB에 적용된다.

사용: uv run python scripts/make_admin.py <이메일> [--revoke]
"""

import sys
from pathlib import Path

from sqlmodel import Session, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.models import User  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    email, revoke = sys.argv[1], "--revoke" in sys.argv[2:]
    with Session(create_engine(settings.db_url)) as s:
        user = s.exec(select(User).where(User.email == email)).first()
        if user is None:
            print(f"가입한 계정이 없습니다: {email}")
            sys.exit(1)
        user.role = "user" if revoke else "admin"
        s.add(user)
        s.commit()
        print(f"{user.name} ({email}) -> {user.role}")


if __name__ == "__main__":
    main()
