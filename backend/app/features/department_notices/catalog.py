"""Reviewed allowlist. Department and source IDs are independent of enrollment rights."""

import json
from pathlib import Path

from pydantic import BaseModel


class DepartmentOut(BaseModel):
    id: str
    name: str
    college: str
    source_ids: list[str]
    note: str


class SourceOut(BaseModel):
    id: str
    name: str
    url: str
    kind: str


_data = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))
DEPARTMENTS = {d["id"]: DepartmentOut(**d) for d in _data["departments"]}
SOURCES = {s["id"]: SourceOut(**s) for s in _data["sources"]}
