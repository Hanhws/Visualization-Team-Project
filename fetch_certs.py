#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_certs.py — data.js 의 1,640편 각각의 연령 등급을 TMDB에서 받아 data/certs.json 저장.
등급은 한국(KR) 우선, 없으면 미국(US) 등급을 한국식(전체/12/15/19)으로 근사 매핑한다.
  - 영화: /movie/{id}/release_dates  (국가별 certification)
  - TV  : /tv/{id}/content_ratings   (국가별 rating)
결과: data/certs.json = { "0_634649": "12", "1_73586": "15", ... }   (키 = media_m_id)
"""
import json, os, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

BASE = "https://api.themoviedb.org/3"
OUT = "data/certs.json"


def load_key():
    for line in open("api_key.txt", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    raise SystemExit("api_key.txt 에 키가 없습니다.")


KEY = load_key()
SESSION = requests.Session()

# ── 등급 문자열 → 한국식 코드 (ALL/12/15/19) ──
KR_MAP = {"all": "ALL", "전체": "ALL", "전체관람가": "ALL", "g": "ALL",
          "7": "ALL", "12": "12", "12세이상관람가": "12",
          "15": "15", "15세이상관람가": "15",
          "18": "19", "19": "19", "청소년관람불가": "19"}
US_MOVIE = {"G": "ALL", "PG": "12", "PG-13": "15", "R": "19", "NC-17": "19"}
US_TV = {"TV-Y": "ALL", "TV-Y7": "ALL", "TV-G": "ALL", "TV-PG": "12",
         "TV-14": "15", "TV-MA": "19"}


def norm_kr(s):
    if not s:
        return None
    return KR_MAP.get(str(s).strip().lower()) or KR_MAP.get(str(s).strip())


def api(path):
    for attempt in range(6):
        try:
            r = SESSION.get(f"{BASE}/{path}", params={"api_key": KEY}, timeout=15)
        except requests.RequestException:
            time.sleep(min(2 ** attempt, 20)); continue
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 2))); continue
        if r.status_code >= 500:
            time.sleep(min(2 ** attempt, 20)); continue
        if r.status_code == 200:
            return r.json()
        return None
    return None


def cert_for(m, tid):
    if m == 0:  # movie
        data = api(f"movie/{tid}/release_dates")
        if not data:
            return None
        by = {}
        for res in data.get("results", []):
            cc = res["iso_3166_1"]
            certs = [d.get("certification") for d in res.get("release_dates", []) if d.get("certification")]
            if certs:
                by[cc] = certs[0]
        if "KR" in by and norm_kr(by["KR"]):
            return norm_kr(by["KR"])
        if "US" in by and by["US"] in US_MOVIE:
            return US_MOVIE[by["US"]]
    else:  # tv
        data = api(f"tv/{tid}/content_ratings")
        if not data:
            return None
        by = {res["iso_3166_1"]: res.get("rating") for res in data.get("results", [])}
        if by.get("KR") and norm_kr(by["KR"]):
            return norm_kr(by["KR"])
        if by.get("US") in US_TV:
            return US_TV[by["US"]]
    return None


def main():
    s = open("data.js", encoding="utf-8").read().strip()
    d = json.loads(s[s.find("=") + 1:].strip().rstrip(";"))
    titles = d["titles"]
    print(f"▶ 등급 수집 시작: {len(titles)}편")

    result = {}
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(cert_for, t["m"], t["id"]): f'{t["m"]}_{t["id"]}' for t in titles}
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                c = fut.result()
            except Exception:
                c = None
            if c:
                result[key] = c
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(titles)} · 등급 확인 {len(result)}건")

    os.makedirs("data", exist_ok=True)
    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    from collections import Counter
    dist = Counter(result.values())
    print(f"✅ 저장: {OUT}  · 등급 있는 작품 {len(result)}/{len(titles)}편")
    print("   분포:", dict(dist))


if __name__ == "__main__":
    main()
