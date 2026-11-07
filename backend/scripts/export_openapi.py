"""API 명세를 frontend/openapi.json으로 내보낸다. 프론트에서 pnpm gen:api가 이걸 읽어 타입을 만든다.

실행 (backend 폴더에서): uv run python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

out = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"저장: {out}")
