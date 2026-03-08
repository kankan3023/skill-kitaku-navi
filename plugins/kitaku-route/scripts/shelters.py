#!/usr/bin/env python3
"""東京都オープンデータから避難場所を取得し、ルート沿いの施設を抽出する"""

import csv
import io
import json
import sys
import urllib.request

# 東京都オープンデータ: 避難場所一覧
EVACUATION_AREA_URL = "https://www.opendata.metro.tokyo.lg.jp/soumu/130001_evacuation_area.csv"


def fetch_shelters() -> list:
    """東京都の避難場所CSVをダウンロードしてパースする"""
    req = urllib.request.Request(EVACUATION_AREA_URL, headers={"User-Agent": "kitaku-route-skill/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(raw))
    shelters = []
    for row in reader:
        try:
            lat = float(row.get("緯度", "").strip())
            lng = float(row.get("経度", "").strip())
        except (ValueError, AttributeError):
            continue

        # 災害種別フラグ
        disaster_types = []
        for dtype in ["洪水", "地震", "津波", "高潮", "大規模な火事", "内水氾濫", "崖崩れ、土石流及び地滑り"]:
            if row.get(dtype, "").strip() == "1":
                disaster_types.append(dtype)

        shelters.append({
            "name": row.get("施設名", "").strip(),
            "address": row.get("所在地住所", "").strip(),
            "municipality": row.get("区市町村", "").strip(),
            "lat": lat,
            "lng": lng,
            "disaster_types": disaster_types,
        })

    return shelters


def distance_deg(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """2点間の概算距離をメートルで返す（東京付近）"""
    dlat = (lat2 - lat1) * 111_000
    dlng = (lng2 - lng1) * 91_000
    return (dlat**2 + dlng**2) ** 0.5


def filter_along_route(shelters: list, coordinates: list, max_distance_m: float = 500) -> list:
    """ルート座標列から一定距離内の避難場所を抽出する"""
    # ルート座標を間引いてチェック（全座標だと遅い）
    step = max(1, len(coordinates) // 50)
    sampled_coords = coordinates[::step]

    nearby = []
    seen = set()
    for shelter in shelters:
        if shelter["name"] in seen:
            continue
        for coord in sampled_coords:
            dist = distance_deg(shelter["lat"], shelter["lng"], coord[1], coord[0])
            if dist <= max_distance_m:
                shelter["distance_m"] = round(dist)
                nearby.append(shelter)
                seen.add(shelter["name"])
                break

    # 距離順でソート
    nearby.sort(key=lambda x: x.get("distance_m", 9999))
    return nearby


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "使い方: shelters.py <ルートGeoJSONファイルパス>"}))
        sys.exit(1)

    geojson_path = sys.argv[1]
    with open(geojson_path, encoding="utf-8") as f:
        geojson = json.load(f)

    coordinates = geojson["features"][0]["geometry"]["coordinates"]

    print("東京都避難場所データを取得中...", file=sys.stderr)
    shelters = fetch_shelters()
    print(f"  全 {len(shelters)} 件取得", file=sys.stderr)

    nearby = filter_along_route(shelters, coordinates, max_distance_m=500)
    print(f"  ルート沿い {len(nearby)} 件抽出", file=sys.stderr)

    output = {
        "shelters": nearby,
        "total_count": len(shelters),
        "nearby_count": len(nearby),
    }

    output_path = "/tmp/kitaku_shelters.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    result = {"shelters_path": output_path, "nearby_count": len(nearby)}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
