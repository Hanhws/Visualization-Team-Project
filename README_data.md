# Nerfle 데이터 가이드 (TMDB → 전처리용)

각 나라 넷플릭스에서 제공하는 영화/TV 목록을 TMDB API로 받아 정리한 데이터입니다.

## 1. 데이터 뽑기

```bash
# 1) API 키 설정 (한 번만)
export TMDB_API_KEY="본인_TMDB_키"

# 2) 실행
python3 fetch_tmdb.py
```

실행하면 터미널에 **컬럼 목록·나라별 건수·미리보기**가 출력되고, 아래 파일이 생깁니다.

| 파일 | 내용 |
|---|---|
| `data/nerfle_titles.csv` | **전처리는 이 파일로.** 모든 나라·작품을 한 테이블로 합친 것 |
| `data/raw/*.json` | API 원본 응답(나라·종류별). 백업/재현용, 건드리지 않음 |

> 조절: `fetch_tmdb.py` 상단 `COUNTRIES`(나라), `MEDIA_TYPES`(movie/tv), `MAX_PAGES`(양) 만 바꾸면 됩니다. 처음엔 `MAX_PAGES=3`으로 가볍게 확인하세요.

## 2. 컬럼(데이터 사전)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `country_code` | str | 국가코드 (KR, JP, US …) |
| `country` | str | 국가명(한글) |
| `media_type` | str | `movie` 또는 `tv` |
| `tmdb_id` | int | TMDB 작품 고유 ID (`media_type`과 함께 써야 유일) |
| `title` | str | 제목(한국어 우선) |
| `original_title` | str | 원제 |
| `original_language` | str | 원어 코드 (en, ja …) |
| `release_date` | str | 개봉일 / 첫 방영일 (YYYY-MM-DD) |
| `genre_ids` | str | 장르 ID 목록 (쉼표구분) |
| `genres` | str | 장르 이름 목록 (쉼표구분) |
| `popularity` | float | TMDB 인기 점수 |
| `vote_average` | float | 평점 (0~10) |
| `vote_count` | int | 평가 수 |
| `overview` | str | 줄거리 |
| `poster_path` | str | 포스터 경로. 실제 이미지 URL은 `https://image.tmdb.org/t/p/w500` + poster_path |
| `only_abroad` | bool | **True면 한국(KR) 넷플릭스엔 없는 작품** = Nerfle 핵심 지표 |

## 3. 전처리 시 알아둘 점

- **유일키는 `(media_type, tmdb_id)`** 조합입니다. 나라별로 같은 작품이 중복 등장하니 join/dedupe 시 주의.
- `release_date`는 빈 문자열일 수 있음 → `pd.to_datetime(..., errors="coerce")` 권장.
- `genres`가 비어있는 행 존재 가능 (장르 미분류 작품).
- `only_abroad`는 "우리가 수집한 KR 목록" 기준이라 `MAX_PAGES`가 작으면 과대추정될 수 있음. 정밀 비교가 필요하면 KR의 `MAX_PAGES`를 크게 두세요.
- 포스터 표시 예: `이미지URL = "https://image.tmdb.org/t/p/w500" + poster_path`

## 4. 고지

This product uses the TMDB API but is not endorsed or certified by TMDB.
