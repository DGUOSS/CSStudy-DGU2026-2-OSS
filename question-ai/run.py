"""python run.py --course demo   (프로필 재생성: --new-profile, 캐시 무시: --no-cache)"""
import argparse

from qgen import pipeline  # pip install -e . (requirements.txt에 포함) 후 사용 가능

ap = argparse.ArgumentParser()
ap.add_argument("--course", default="demo")
ap.add_argument("--run-id")
ap.add_argument("--new-profile", action="store_true")
ap.add_argument("--no-cache", action="store_true")
a = ap.parse_args()
pipeline.run(a.course, a.run_id, new_profile=a.new_profile, use_cache=not a.no_cache)
