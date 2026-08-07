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

# 수집 대상 나라: True 면 넷플릭스가 서비스되는 전 세계 국가(약 128개국)를 TMDB에서
# 자동으로 받아와 모두 수집합니다. False 면 아래 COUNTRIES_MANUAL 목록만 씁니다.
AUTO_DISCOVER_COUNTRIES = True

# (AUTO_DISCOVER_COUNTRIES=False 일 때만 사용) 직접 지정할 나라 목록
COUNTRIES_MANUAL = {
    "KR": "대한민국", "JP": "일본", "US": "미국", "GB": "영국", "FR": "프랑스", "TH": "태국",
}

# 기준국: 이 나라에 '없는' 작품을 '한국 미제공(only_abroad)'으로 표시. 항상 포함됩니다.
REFERENCE = "KR"

# 수집할 미디어 종류: "movie", "tv" 중 원하는 것
MEDIA_TYPES = ["movie", "tv"]

# 나라·종류별로 가져올 페이지 수 (1페이지 = 20편). TMDB discover 최대 500페이지.
PAGES_PER_COUNTRY = 25     # 일반 국가: 인기순 상위 ~500편/종류 (숫자 올리면 더 많이 수집)
PAGES_REFERENCE   = 200    # 기준국(한국): 비교 정확도 위해 깊게 (~4,000편/종류)

# 채워지는 실제 나라 목록 (main 에서 설정). {코드: 표시이름}
COUNTRIES = dict(COUNTRIES_MANUAL)

NETFLIX_PROVIDER_ID = 8       # TMDB 기준 넷플릭스 provider id
LANGUAGE = "ko-KR"            # 제목·줄거리 언어 (없으면 원어로 옴)
OUTPUT_DIR = "data"

# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://api.themoviedb.org/3"
SESSION = requests.Session()


def api_get(path, **params):
    """TMDB API GET 요청 + 레이트리밋·네트워크 오류 재시도 처리."""
    params["api_key"] = API_KEY
    url = f"{BASE_URL}/{path}"
    for attempt in range(8):
        try:
            r = SESSION.get(url, params=params, timeout=20)
        except requests.exceptions.RequestException as e:   # 연결 끊김/타임아웃 등
            wait = min(2 ** attempt, 30)
            print(f"  · 네트워크 오류({type(e).__name__}), {wait}s 후 재시도...")
            time.sleep(wait)
            continue
        if r.status_code == 429:                      # 요청 과다 → 잠깐 대기
            wait = int(r.headers.get("Retry-After", 2))
            print(f"  · 레이트리밋, {wait}s 대기...")
            time.sleep(wait)
            continue
        if r.status_code == 401:
            sys.exit("❌ 인증 실패(401): TMDB_API_KEY 를 확인하세요.")
        if r.status_code >= 500:                       # 서버 오류 → 재시도
            time.sleep(min(2 ** attempt, 30))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"API 요청 실패(재시도 초과): {path}")


def load_genre_map():
    """장르 id → 이름 매핑 (movie/tv 합침)."""
    gmap = {}
    for media in ("movie", "tv"):
        data = api_get(f"genre/{media}/list", language=LANGUAGE)
        for g in data.get("genres", []):
            gmap[g["id"]] = g["name"]
    return gmap


def netflix_countries():
    """넷플릭스(provider 8)가 서비스되는 전 세계 국가 {코드: 이름} 를 TMDB에서 받아온다."""
    regions = api_get("watch/providers/regions", language="ko-KR").get("results", [])
    names = {r["iso_3166_1"]: r.get("native_name", r["iso_3166_1"]) for r in regions}
    found = {}
    for code in names:
        data = api_get("watch/providers/movie", watch_region=code)
        if any(p.get("provider_id") == NETFLIX_PROVIDER_ID for p in data.get("results", [])):
            found[code] = names[code]
    found[REFERENCE] = names.get(REFERENCE, REFERENCE)   # 기준국은 반드시 포함
    return found


def discover_titles(country_code, media_type, max_pages):
    """한 나라·한 종류의 넷플릭스 제공 작품을 인기순으로 max_pages 페이지까지 수집."""
    results = []
    for page in range(1, max_pages + 1):
        data = api_get(
            f"discover/{media_type}",
            language=LANGUAGE,
            watch_region=country_code,
            with_watch_providers=NETFLIX_PROVIDER_ID,
            watch_monetization_types="flatrate",   # 구독으로 볼 수 있는 것만
            sort_by="popularity.desc",
            page=page,
        )
        results.extend(data.get("results", []))
        if page >= data.get("total_pages", 1):
            break
        time.sleep(0.05)   # 예의상 살짝 쉬기 (429 나면 자동 재시도)
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

    global COUNTRIES
    if AUTO_DISCOVER_COUNTRIES:
        print("▶ 넷플릭스 제공 국가 목록 받아오는 중...", end=" ", flush=True)
        COUNTRIES = netflix_countries()
        print(f"{len(COUNTRIES)}개국")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_dir = os.path.join(OUTPUT_DIR, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    print("▶ 장르 매핑 불러오는 중...")
    genre_map = load_genre_map()

    # 기준국(한국)을 맨 앞에 두고 순회 (비교 기준을 먼저 확보)
    order = [REFERENCE] + [c for c in COUNTRIES if c != REFERENCE]
    all_rows = []
    for i, code in enumerate(order, 1):
        cap = PAGES_REFERENCE if code == REFERENCE else PAGES_PER_COUNTRY
        for media in MEDIA_TYPES:
            print(f"[{i}/{len(order)}] {COUNTRIES.get(code, code)}({code}) · {media} ...",
                  end=" ", flush=True)
            items = discover_titles(code, media, cap)
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
