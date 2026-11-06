"""backend/.env의 DATABASE_URL로 DB에 접속되는지 확인한다. 실행: uv run python scripts/check_db.py"""
import os
from pathlib import Path

from sqlalchemy import create_engine, text

env = Path(__file__).resolve().parents[1] / ".env"
for line in env.read_text(encoding="utf-8").splitlines() if env.exists() else []:
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

url = os.environ.get("DATABASE_URL", "")
if not url:
    raise SystemExit("backend/.env에 DATABASE_URL이 없습니다")
url = url.replace("postgresql://", "postgresql+psycopg://", 1) if url.startswith("postgresql://") else url
with create_engine(url).connect() as conn:
    print("DB 연결 성공:", conn.execute(text("select version()")).scalar())
