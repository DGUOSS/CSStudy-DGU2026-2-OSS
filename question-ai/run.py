"""python run.py --course demo   (프로필 재생성: --new-profile, 캐시 무시: --no-cache, 검증 없이 생성만: --no-verify)"""
import argparse
import sys

from qgen import pipeline  # pip install -e . (requirements.txt에 포함) 후 사용 가능

# Windows 기본 콘솔(cp949)은 ✗ 같은 기호를 출력하지 못해 실행이 멈춘다 → 출력은 UTF-8로
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ap = argparse.ArgumentParser()
ap.add_argument("--course", default="demo")
ap.add_argument("--run-id")
ap.add_argument("--new-profile", action="store_true")
ap.add_argument("--no-cache", action="store_true")
ap.add_argument("--no-verify", action="store_true", help="solver·reviewer 검증과 수정 없이 generator 1번으로 시험지 생성")
a = ap.parse_args()
pipeline.run(a.course, a.run_id, new_profile=a.new_profile, use_cache=not a.no_cache, verify=not a.no_verify)
