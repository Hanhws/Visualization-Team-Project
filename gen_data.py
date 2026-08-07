#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nerfle_titles.csv -> data.js (웹앱용 가공 데이터 생성)
한국 미제공(only_abroad) 작품을 나라별로 묶고, 검색용 전체 목록을 만든다.
지도 하이라이트를 위해 ISO2 -> ISO3166 숫자코드(topojson id) 매핑을 포함한다."""
import pandas as pd, json

# ISO 3166-1 alpha-2 -> 숫자코드 (world-atlas topojson 의 feature.id 와 매칭)
ISO2NUM = {"AF": "004", "AX": "248", "AL": "008", "DZ": "012", "AS": "016", "AD": "020", "AO": "024", "AI": "660", "AQ": "010", "AG": "028", "AR": "032", "AM": "051", "AW": "533", "AU": "036", "AT": "040", "AZ": "031", "BS": "044", "BH": "048", "BD": "050", "BB": "052", "BY": "112", "BE": "056", "BZ": "084", "BJ": "204", "BM": "060", "BT": "064", "BO": "068", "BQ": "535", "BA": "070", "BW": "072", "BV": "074", "BR": "076", "IO": "086", "BN": "096", "BG": "100", "BF": "854", "BI": "108", "CV": "132", "KH": "116", "CM": "120", "CA": "124", "KY": "136", "CF": "140", "TD": "148", "CL": "152", "CN": "156", "CX": "162", "CC": "166", "CO": "170", "KM": "174", "CG": "178", "CD": "180", "CK": "184", "CR": "188", "CI": "384", "HR": "191", "CU": "192", "CW": "531", "CY": "196", "CZ": "203", "DK": "208", "DJ": "262", "DM": "212", "DO": "214", "EC": "218", "EG": "818", "SV": "222", "GQ": "226", "ER": "232", "EE": "233", "SZ": "748", "ET": "231", "FK": "238", "FO": "234", "FJ": "242", "FI": "246", "FR": "250", "GF": "254", "PF": "258", "TF": "260", "GA": "266", "GM": "270", "GE": "268", "DE": "276", "GH": "288", "GI": "292", "GR": "300", "GL": "304", "GD": "308", "GP": "312", "GU": "316", "GT": "320", "GG": "831", "GN": "324", "GW": "624", "GY": "328", "HT": "332", "HM": "334", "VA": "336", "HN": "340", "HK": "344", "HU": "348", "IS": "352", "IN": "356", "ID": "360", "IR": "364", "IQ": "368", "IE": "372", "IM": "833", "IL": "376", "IT": "380", "JM": "388", "JP": "392", "JE": "832", "JO": "400", "KZ": "398", "KE": "404", "KI": "296", "KP": "408", "KR": "410", "KW": "414", "KG": "417", "LA": "418", "LV": "428", "LB": "422", "LS": "426", "LR": "430", "LY": "434", "LI": "438", "LT": "440", "LU": "442", "MO": "446", "MG": "450", "MW": "454", "MY": "458", "MV": "462", "ML": "466", "MT": "470", "MH": "584", "MQ": "474", "MR": "478", "MU": "480", "YT": "175", "MX": "484", "FM": "583", "MD": "498", "MC": "492", "MN": "496", "ME": "499", "MS": "500", "MA": "504", "MZ": "508", "MM": "104", "NA": "516", "NR": "520", "NP": "524", "NL": "528", "NC": "540", "NZ": "554", "NI": "558", "NE": "562", "NG": "566", "NU": "570", "NF": "574", "MK": "807", "MP": "580", "NO": "578", "OM": "512", "PK": "586", "PW": "585", "PS": "275", "PA": "591", "PG": "598", "PY": "600", "PE": "604", "PH": "608", "PN": "612", "PL": "616", "PT": "620", "PR": "630", "QA": "634", "RE": "638", "RO": "642", "RU": "643", "RW": "646", "BL": "652", "SH": "654", "KN": "659", "LC": "662", "MF": "663", "PM": "666", "VC": "670", "WS": "882", "SM": "674", "ST": "678", "SA": "682", "SN": "686", "RS": "688", "SC": "690", "SL": "694", "SG": "702", "SX": "534", "SK": "703", "SI": "705", "SB": "090", "SO": "706", "ZA": "710", "GS": "239", "SS": "728", "ES": "724", "LK": "144", "SD": "729", "SR": "740", "SJ": "744", "SE": "752", "CH": "756", "SY": "760", "TW": "158", "TJ": "762", "TZ": "834", "TH": "764", "TL": "626", "TG": "768", "TK": "772", "TO": "776", "TT": "780", "TN": "788", "TR": "792", "TM": "795", "TC": "796", "TV": "798", "UG": "800", "UA": "804", "AE": "784", "GB": "826", "US": "840", "UM": "581", "UY": "858", "UZ": "860", "VU": "548", "VE": "862", "VN": "704", "VG": "092", "VI": "850", "WF": "876", "EH": "732", "YE": "887", "ZM": "894", "ZW": "716"}

CSV = "data/nerfle_titles.csv"

def poster(p): return f"https://image.tmdb.org/t/p/w342{p}" if isinstance(p,str) and p else ""
def year(d):   return str(d)[:4] if isinstance(d,str) and d else ""

def rec(r):
    return {
        "title": r["title"] if isinstance(r["title"],str) else (r.get("original_title") or ""),
        "media_type": r["media_type"],
        "poster": poster(r.get("poster_path")),
        "year": year(r.get("release_date")),
        "genres": r["genres"] if isinstance(r["genres"],str) else "",
        "vote": round(float(r["vote_average"]),1) if pd.notna(r["vote_average"]) else None,
    }

def main():
    df = pd.read_csv(CSV)
    ab = df[df["only_abroad"] == True].copy()

    countries = {}
    for code, g in ab.groupby("country_code"):
        g = g.sort_values("popularity", ascending=False)
        countries[code] = {
            "name": g.iloc[0]["country"],
            "iso2": code,
            "id": ISO2NUM.get(code, ""),
            "count": int(len(g)),
            "programs": [rec(r) for _, r in g.iterrows()],
        }

    # 검색용 전체 목록: 같은 작품이 여러 나라에 걸쳐 중복되므로 tmdb_id 기준 1개만.
    # 대신 그 작품을 볼 수 있는 나라 목록(available_in)을 함께 담는다.
    ctry_by_id = (ab.groupby(["media_type", "tmdb_id"])["country"]
                    .apply(lambda s: sorted(set(s))).to_dict())
    allp = []
    seen = set()
    for _, r in ab.sort_values("popularity", ascending=False).iterrows():
        key = (r["media_type"], r["tmdb_id"])
        if key in seen:
            continue
        seen.add(key)
        d = rec(r)
        countries_avail = ctry_by_id.get(key, [])
        d["country"] = countries_avail[0] if countries_avail else r["country"]
        d["available_in"] = countries_avail
        allp.append(d)

    data = {"countries": countries, "all": allp,
            "meta": {"total": int(len(ab)), "n_countries": int(ab["country_code"].nunique())}}
    with open("data.js", "w", encoding="utf-8") as f:
        f.write("window.NERFLE = "); json.dump(data, f, ensure_ascii=False); f.write(";")

    print(f"data.js 생성: {len(countries)}개국, 한국 미제공 {len(ab):,}편")

if __name__ == "__main__":
    main()
