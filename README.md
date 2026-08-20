# NERFLE (너플) — 너에게 없는 넷플릭스

> 너플은 **한국 넷플릭스에는 없지만, 해외에는 있는 작품들**을 한눈에 보여주는 **데이터 시각화 웹앱**입니다.
> 넷플릭스에서 국가마다 서비스하고 있는 콘텐츠가 다릅니다. 한국에서 검색했을 땐 나오지 않지만 다른 국가에선 서비스 중인 콘텐츠인 것을 발견했을때, 해당 국가를 여행하게 된다면 꼭 보리라 생각하게 됩니다.
> 너플은 이러한 문제 상황에서 출발하게 되었습니다. 너플을 이용하면 한국 넷플릭스에는 무엇이 빠져있는지 국가별로 서비스 중인 콘텐츠를 세계지도로 확인하거나, 혹은 작품 별로 서비스 되고 있는 국가를 찾을 수 있습니다.
> 
> 본 서비스는 TMDB에서 데이터를 제공 받아 126개국의 넷플릭스 스트리밍 현황을 확인하였습니다.

🔗 **라이브 사이트** — https://visualization-team-project.vercel.app
🎞 **발표 슬라이드** — https://visualization-team-project.vercel.app/deck

SNU KDT · 데이터 시각화 팀 프로젝트 (6조)

---

## ✨ 주요 기능

- **세계지도** — 나라별 한국 미제공 작품 수를 색으로 시각화 (D3.js), 클릭·검색·확대
- **작품 탐색** — 장르·평점·제공 국가 수 등으로 필터링
- **인사이트 대시보드** — 장르별 분포, 공개 연도별 추이, 콘텐츠 부자 나라 랭킹
- **나라 vs 나라** — 두 나라 카탈로그 비교
- **찜 · 넷플릭스 여권** — 로그인 없이 `localStorage`로 저장, 최소 몇 개국이면 다 볼 수 있는지 계산

## 🧱 기술 스택

- **프론트엔드** — Vanilla JS, [D3.js](https://d3js.org/) (지도/차트), 단일 `data.js`로 서빙
- **데이터** — [TMDB API](https://www.themoviedb.org/) 기반 126개국 넷플릭스 카탈로그 수집·정규화
- **파이프라인** — Python
- **배포** — Vercel (GitHub `main` 푸시 시 자동 배포, `cleanUrls`)

## 📁 폴더 구조

```
.
├── index.html          # 메인 웹앱 (지도·탐색·대시보드)
├── deck.html           # 발표 슬라이드 (→ /deck)
├── data.js             # 웹앱이 사용하는 가공 데이터 (파이프라인 산출물)
├── vercel.json         # 배포 설정 (cleanUrls)
│
├── scripts/            # 데이터 파이프라인 (레포 루트에서 실행)
│   ├── fetch_tmdb.py   #  ① TMDB에서 126개국 카탈로그 수집 → data/
│   ├── fetch_certs.py  #  ② 작품별 연령 등급 수집 → data/certs.json
│   ├── build_data.py   #  ③ 정규화·집계 → data.js  (메인)
│   └── gen_data.py     #     (구버전 생성 스크립트)
│
├── data/               # 중간 산출물 (대용량 원본은 .gitignore)
├── docs/               # 발표대본·발표자료·제출 PDF·데이터 설명
├── archive/            # 초기 프로토타입 (dashboard.html, tmdb-explorer.html)
└── 영상/               # 광고 영상 (슬라이드 5에 임베드)
```

## 🚀 로컬 실행

```bash
# 정적 서버로 열기 (data.js 를 fetch 하므로 file:// 대신 서버 권장)
python3 -m http.server 8000
# → http://localhost:8000        (메인 사이트)
# → http://localhost:8000/deck.html  (발표 슬라이드)
```

## 🔧 데이터 다시 만들기

> `scripts/` 는 **레포 루트에서** 실행하세요 (경로가 루트 기준입니다).
> TMDB API 키는 루트에 `api_key.txt` 로 두거나 환경변수 `TMDB_API_KEY` 로 지정합니다.
> (`api_key.txt.example` 참고 — 실제 키 파일은 `.gitignore` 처리됨)

```bash
python3 scripts/fetch_tmdb.py    # ① 126개국 카탈로그 수집
python3 scripts/fetch_certs.py   # ② 연령 등급 수집
python3 scripts/build_data.py    # ③ data.js 생성
```

## 📝 라이선스 / 출처

- 콘텐츠 메타데이터: **TMDB** (본 서비스는 TMDB가 보증하지 않음)
- 본 프로젝트는 **정보 제공용**이며, 우회 접속을 제공하지 않습니다.
