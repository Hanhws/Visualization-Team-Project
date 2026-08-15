#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_data.py — nerfle_titles.csv → data.js (정규화 + 집계판)
=============================================================
기존 gen_data.py 는 작품을 나라마다 통째로 복사해 담아 6.3MB로 비대했다.
이 스크립트는 '한국 미제공(only_abroad)' 고유 작품 1벌만 담고, 나라는 인덱스로 참조해
용량을 줄이면서 아래 모든 기능이 요구하는 데이터를 한 번에 만든다.

담는 것
  - countries : [{code,name,id,n}]  (id=world-atlas topojson 숫자코드, n=그 나라 미제공 작품 수)
  - genres    : {장르id: 이름}
  - titles    : 고유 작품 1벌. 필드는 용량을 위해 짧게.
        t  제목        ot 원제        m 0=movie/1=tv   y 연도(int)
        g  [장르id]    v 평점         vc 평가수         pop 인기도
        ol 원어        p  포스터경로   ov 줄거리
        av [나라인덱스]  (이 작품을 볼 수 있는 나라들 → countries 인덱스)
  - stats     : 대시보드/스토리텔링용 사전집계
        total_unique, total_rows, n_countries,
        genre_counts, year_hist, country_rank(독점률), country_top_genres,
        lang_counts, generated_at
설계 메모
  - 포스터 URL = "https://image.tmdb.org/t/p/w342" + p  (접두어 반복 제거)
  - '희소성'(몇 개국에서만 서비스) = len(av). 낮을수록 진짜 숨은 작품.
  - '지금 뜨는 것'은 스냅샷 1개라 진짜 급상승은 계산 불가 → pop 상위로 근사(웹에서 라벨링).
"""
import json, math, os
from datetime import datetime, timezone

import pandas as pd
from gen_data import ISO2NUM   # ISO2 → topojson 숫자코드 매핑 재사용

CSV = "data/nerfle_titles.csv"
OUT = "data.js"


def year_of(d):
    s = str(d)
    return int(s[:4]) if len(s) >= 4 and s[:4].isdigit() else None


def main():
    df = pd.read_csv(CSV)
    total_rows = int((df["only_abroad"] == True).sum())
    ab = df[df["only_abroad"] == True].copy()

    # 연령 등급(있으면): fetch_certs.py 가 만든 data/certs.json = {"m_id": "15"}
    certs = {}
    if os.path.exists("data/certs.json"):
        certs = json.load(open("data/certs.json", encoding="utf-8"))

    # ── 장르 id → 이름 매핑 (데이터 안의 genre_ids/genres 쌍에서 복원) ──
    gmap = {}
    for ids, names in zip(ab["genre_ids"].dropna(), ab["genres"].dropna()):
        ids = [x for x in str(ids).split(",") if x]
        names = [x.strip() for x in str(names).split(",")]
        for i, n in zip(ids, names):
            gmap.setdefault(int(i), n)

    # ── 나라 목록 (코드→이름), only_abroad 작품이 존재하는 나라만 ──
    name_by_code = ab.groupby("country_code")["country"].first().to_dict()
    codes = sorted(name_by_code, key=lambda c: name_by_code[c])
    cidx = {c: i for i, c in enumerate(codes)}          # 코드 → 인덱스
    countries = [{"code": c, "name": name_by_code[c],
                  "id": ISO2NUM.get(c, ""), "n": 0} for c in codes]

    # ── 작품별 가용 국가(인덱스) 모으기 ──
    av_by_key = {}
    for key, g in ab.groupby(["media_type", "tmdb_id"]):
        idxs = sorted({cidx[c] for c in g["country_code"] if c in cidx})
        av_by_key[key] = idxs
        for i in idxs:
            countries[i]["n"] += 1

    # ── 고유 작품 1벌 만들기 (인기순) ──
    titles = []
    seen = set()
    for _, r in ab.sort_values("popularity", ascending=False).iterrows():
        key = (r["media_type"], r["tmdb_id"])
        if key in seen:
            continue
        seen.add(key)
        gids = [int(x) for x in str(r["genre_ids"]).split(",") if x.strip().isdigit()] \
            if pd.notna(r["genre_ids"]) else []
        title = r["title"] if isinstance(r["title"], str) and r["title"].strip() \
            else (r.get("original_title") or "")
        _mid = f'{0 if r["media_type"] == "movie" else 1}_{int(r["tmdb_id"])}' \
            if pd.notna(r["tmdb_id"]) else ""
        titles.append({
            "id": int(r["tmdb_id"]) if pd.notna(r["tmdb_id"]) else 0,
            "cr": certs.get(_mid, ""),   # 연령 등급 (ALL/12/15/19), 없으면 ""
            "t": title,
            "ot": r["original_title"] if isinstance(r["original_title"], str) else "",
            "m": 1 if r["media_type"] == "tv" else 0,
            "y": year_of(r.get("release_date")),
            "g": gids,
            "v": round(float(r["vote_average"]), 1) if pd.notna(r["vote_average"]) else None,
            "vc": int(r["vote_count"]) if pd.notna(r["vote_count"]) else 0,
            "pop": round(float(r["popularity"]), 1) if pd.notna(r["popularity"]) else 0,
            "ol": r["original_language"] if isinstance(r["original_language"], str) else "",
            "p": r["poster_path"] if isinstance(r["poster_path"], str) else "",
            "ov": (r["overview"] if isinstance(r["overview"], str) else "")[:300],
            "av": av_by_key[key],
        })

    # ── 집계(stats) ──
    genre_counts, year_hist, lang_counts = {}, {}, {}
    for t in titles:
        for gid in t["g"]:
            genre_counts[gid] = genre_counts.get(gid, 0) + 1
        if t["y"]:
            year_hist[t["y"]] = year_hist.get(t["y"], 0) + 1
        if t["ol"]:
            lang_counts[t["ol"]] = lang_counts.get(t["ol"], 0) + 1

    country_rank = sorted(
        [{"code": c["code"], "name": c["name"], "n": c["n"]} for c in countries],
        key=lambda x: -x["n"])

    # 나라별 대표 장르 top5 (콘텐츠 특색 프로파일)
    country_genre = {c["code"]: {} for c in countries}
    for t in titles:
        for i in t["av"]:
            code = countries[i]["code"]
            for gid in t["g"]:
                country_genre[code][gid] = country_genre[code].get(gid, 0) + 1
    country_top_genres = {
        code: sorted(gd.items(), key=lambda kv: -kv[1])[:5]
        for code, gd in country_genre.items()}

    stats = {
        "total_unique": len(titles),
        "total_rows": total_rows,
        "n_countries": len(countries),
        "genre_counts": genre_counts,
        "year_hist": year_hist,
        "lang_counts": lang_counts,
        "country_rank": country_rank,
        "country_top_genres": country_top_genres,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    data = {"countries": countries, "genres": {str(k): v for k, v in gmap.items()},
            "titles": titles, "stats": stats}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.NERFLE = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";")

    print(f"✅ {OUT} 생성  ({os.path.getsize(OUT)/1e6:.2f} MB)")
    print(f"   등급 표기: {sum(1 for t in titles if t['cr'])}/{len(titles)}편")
    print(f"   고유 작품 {len(titles):,}편 · 나라 {len(countries)}개 · 장르 {len(gmap)}종")
    print(f"   (나라별 중복 포함 총 {total_rows:,} 행 → 고유 {len(titles):,} 편으로 정규화)")
    print(f"   독점률 top5: " + ", ".join(f"{r['name']}({r['n']})" for r in country_rank[:5]))


if __name__ == "__main__":
    main()
