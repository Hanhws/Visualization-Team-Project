#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nerfle - TMDB 넷플릭스 국가별 카탈로그 수집 스크립트
=====================================================
각 나라 넷플릭스(TMDB provider id = 8)에서 제공하는 영화/TV 목록을 받아
- data/raw/*.json  : API 원본 응답(전처리 전, 백업/재현용)
- data/nerfle_titles.csv : 팀원 전처리용 통합 테이블
로 저장합니다. 한국(KR) 카탈로그와 비교해 '한국 미제공' 여부(only_abroad)도 붙입니다.

[사용법]
  1) TMDB API 키 준비 (https://www.themoviedb.org/settings/api)
  2) 아래 방법 중 하나로 키 전달:
       터미널:  export TMDB_API_KEY="여기에_키"
       또는:    아래 API_KEY 변수에 직접 붙여넣기
  3) 실행:      python3 fetch_tmdb.py

[조절 포인트]  아래 CONFIG 섹션의 COUNTRIES / MEDIA_TYPES / MAX_PAGES 만 바꾸면 됩니다.
"""

import os
import sys
import json
import time
from datetime import datetime

import requests
import pandas as pd

# ─────────────────────────── CONFIG (여기만 바꾸면 됨) ───────────────────────────

def _load_api_key():
    """API 키를 (1)환경변수 → (2)api_key.txt 파일 순으로 찾는다."""
    key = os.environ.get("TMDB_API_KEY", "").strip()
    if key:
        return key
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_key.txt")
    if os.path.exists(key_file):
        with open(key_file, encoding="utf-8") as f:
            # 주석(#)·빈 줄 무시하고 첫 유효한 줄을 키로 사용
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    return ""

# API 키: 환경변수 우선, 없으면 같은 폴더의 api_key.txt 파일에서 읽음.
API_KEY = _load_api_key() or "여기에_TMDB_API_KEY_붙여넣기"

# 수집할 나라 (ISO-3166-1 2글자 국가코드). 기준국인 한국(KR)은 비교용으로 항상 포함됩니다.
COUNTRIES = {
    "KR": "대한민국",
    "JP": "일본",
    "US": "미국",
    "GB": "영국",
    "FR": "프랑스",
    "TH": "태국",
}

# 수집할 미디어 종류: "movie", "tv" 중 원하는 것
MEDIA_TYPES = ["movie", "tv"]

# 나라·종류별로 가져올 페이지 수 (1페이지 = 20개). 처음엔 3으로 가볍게 테스트 권장.
MAX_PAGES = 3

NETFLIX_PROVIDER_ID = 8       # TMDB 기준 넷플릭스 provider id
LANGUAGE = "ko-KR"            # 제목·줄거리 언어 (없으면 원어로 옴)
OUTPUT_DIR = "data"

# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://api.themoviedb.org/3"
SESSION = requests.Session()


def api_get(path, **params):
    """TMDB API GET 요청 + 간단한 재시도/레이트리밋 처리."""
    params["api_key"] = API_KEY
    url = f"{BASE_URL}/{path}"
    for attempt in range(4):
        r = SESSION.get(url, params=params, timeout=20)
        if r.status_code == 429:                      # 요청 과다 → 잠깐 대기
            wait = int(r.headers.get("Retry-After", 2))
            print(f"  · 레이트리밋, {wait}s 대기...")
            time.sleep(wait)
            continue
        if r.status_code == 401:
            sys.exit("❌ 인증 실패(401): TMDB_API_KEY 를 확인하세요.")
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def load_genre_map():
    """장르 id → 이름 매핑 (movie/tv 합침)."""
    gmap = {}
    for media in ("movie", "tv"):
        data = api_get(f"genre/{media}/list", language=LANGUAGE)
        for g in data.get("genres", []):
            gmap[g["id"]] = g["name"]
    return gmap


def discover_titles(country_code, media_type):
    """한 나라·한 종류의 넷플릭스 제공 작품을 페이지네이션으로 모두 수집."""
    results = []
    total_pages = None
    for page in range(1, MAX_PAGES + 1):
        data = api_get(
            f"discover/{media_type}",
            language=LANGUAGE,
            watch_region=country_code,
            with_watch_providers=NETFLIX_PROVIDER_ID,
            watch_monetization_types="flatrate",   # 구독으로 볼 수 있는 것만
            sort_by="popularity.desc",
            page=page,
        )
        if total_pages is None:
            total_pages = min(data.get("total_pages", 1), MAX_PAGES)
        results.extend(data.get("results", []))
        if page >= data.get("total_pages", 1):
            break
        time.sleep(0.25)   # 예의상 살짝 쉬기
    return results


def flatten(item, country_code, media_type, genre_map):
    """API 항목 하나를 표(한 행) 형태로 평탄화."""
    # 영화는 title/release_date, TV는 name/first_air_date 로 필드명이 다름 → 통일
    title = item.get("title") or item.get("name")
    orig_title = item.get("original_title") or item.get("original_name")
    date = item.get("release_date") or item.get("first_air_date")
    genre_ids = item.get("genre_ids", [])
    return {
        "country_code": country_code,
        "country": COUNTRIES.get(country_code, country_code),
        "media_type": media_type,
        "tmdb_id": item.get("id"),
        "title": title,
        "original_title": orig_title,
        "original_language": item.get("original_language"),
        "release_date": date,
        "genre_ids": ",".join(map(str, genre_ids)),
        "genres": ", ".join(genre_map.get(g, str(g)) for g in genre_ids),
        "popularity": item.get("popularity"),
        "vote_average": item.get("vote_average"),
        "vote_count": item.get("vote_count"),
        "overview": (item.get("overview") or "").replace("\n", " ").strip(),
        "poster_path": item.get("poster_path"),
    }


def main():
    if API_KEY.startswith("여기에"):
        sys.exit("❌ API 키가 설정되지 않았습니다. 환경변수 TMDB_API_KEY 를 설정하거나 "
                 "스크립트 상단 API_KEY 변수에 키를 넣어주세요.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_dir = os.path.join(OUTPUT_DIR, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    print("▶ 장르 매핑 불러오는 중...")
    genre_map = load_genre_map()

    all_rows = []
    for code in COUNTRIES:
        for media in MEDIA_TYPES:
            print(f"▶ 수집: {COUNTRIES[code]}({code}) · {media} ...", end=" ", flush=True)
            items = discover_titles(code, media)
            # 원본 백업
            raw_path = os.path.join(raw_dir, f"{code}_{media}_{stamp}.json")
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            all_rows.extend(flatten(it, code, media, genre_map) for it in items)
            print(f"{len(items)}건")

    df = pd.DataFrame(all_rows)
    if df.empty:
        sys.exit("⚠️ 수집된 데이터가 없습니다. COUNTRIES/MEDIA_TYPES/MAX_PAGES 를 확인하세요.")

    # ── 한국(KR)과 비교해 '한국 미제공' 여부 표시 ──
    kr_ids = set(df.loc[df["country_code"] == "KR", ["media_type", "tmdb_id"]]
                   .itertuples(index=False, name=None))
    df["only_abroad"] = ~df.apply(
        lambda r: (r["media_type"], r["tmdb_id"]) in kr_ids, axis=1)
    df.loc[df["country_code"] == "KR", "only_abroad"] = False  # 기준국은 항상 False

    csv_path = os.path.join(OUTPUT_DIR, "nerfle_titles.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")   # 엑셀 한글깨짐 방지

    # ─────────────────── 데이터가 어떻게 생겼는지 요약 출력 ───────────────────
    print("\n" + "=" * 60)
    print(f"✅ 저장 완료: {csv_path}  (총 {len(df):,}행)")
    print(f"   원본 JSON: {raw_dir}/  ({len(COUNTRIES)*len(MEDIA_TYPES)}개 파일)")
    print("=" * 60)

    print("\n[컬럼 목록 / 데이터 사전]")
    dtypes = df.dtypes
    for col in df.columns:
        n_null = df[col].isna().sum()
        print(f"  - {col:<18} {str(dtypes[col]):<10} 결측 {n_null}")

    print("\n[나라별 건수]")
    pivot = df.pivot_table(index="country", columns="media_type",
                           values="tmdb_id", aggfunc="count", fill_value=0)
    print(pivot.to_string())

    print("\n[한국 미제공(only_abroad=True) 나라별 건수]")
    print(df[df["only_abroad"]].groupby("country")["tmdb_id"].count().to_string())

    print("\n[미리보기 5행]")
    with pd.option_context("display.max_columns", None, "display.width", 160):
        print(df[["country", "media_type", "title", "genres",
                  "vote_average", "only_abroad"]].head().to_string(index=False))
    print("\n필드 설명은 README_data.md 참고. 전처리는 nerfle_titles.csv 로 진행하세요.")


if __name__ == "__main__":
    main()
