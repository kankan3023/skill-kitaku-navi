#!/usr/bin/env python3
"""Overpass APIを使ったルート沿い施設検索"""

import json
import sys
import time
import urllib.request
import urllib.parse


def sample_route_points(coordinates: list, interval_m: float = 2000) -> list:
    """ルートの座標列から一定間隔でサンプリングする（API負荷軽減）"""
    if not coordinates:
        return []

    sampled = [coordinates[0]]
    accumulated = 0.0

    for i in range(1, len(coordinates)):
        prev = coordinates[i - 1]
        curr = coordinates[i]
        # 簡易距離計算（度→メートル概算）
        dlat = (curr[1] - prev[1]) * 111_000
        dlng = (curr[0] - prev[0]) * 91_000  # 東京付近の概算
        dist = (dlat**2 + dlng**2) ** 0.5
        accumulated += dist

        if accumulated >= interval_m:
            sampled.append(curr)
            accumulated = 0.0

    # 最後の点を必ず含める
    if sampled[-1] != coordinates[-1]:
        sampled.append(coordinates[-1])

    return sampled


def query_overpass(lat: float, lng: float, radius: int = 500) -> list:
    """指定座標周辺の防災関連施設をOverpass APIで検索"""
    query = f"""
[out:json][timeout:25];
(
  node["shop"="convenience"](around:{radius},{lat},{lng});
  node["amenity"="toilets"](around:{radius},{lat},{lng});
  node["amenity"="hospital"](around:{radius},{lat},{lng});
  node["amenity"="clinic"](around:{radius},{lat},{lng});
  node["amenity"="fuel"](around:{radius},{lat},{lng});
  node["emergency"="defibrillator"](around:{radius},{lat},{lng});
  node["amenity"="drinking_water"](around:{radius},{lat},{lng});
  node["leisure"="park"](around:{radius},{lat},{lng});
  way["leisure"="park"](around:{radius},{lat},{lng});
);
out center body;
"""

    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    return result.get("elements", [])


def categorize_facilities(elements: list) -> dict:
    """施設をカテゴリ別に分類する"""
    categories = {
        "convenience": [],      # コンビニ
        "toilets": [],          # トイレ
        "hospital": [],         # 病院
        "clinic": [],           # クリニック
        "fuel": [],             # ガソリンスタンド
        "aed": [],              # AED
        "drinking_water": [],   # 給水ポイント
        "park": [],             # 公園
    }

    seen_ids = set()
    for el in elements:
        if el["id"] in seen_ids:
            continue
        seen_ids.add(el["id"])

        tags = el.get("tags", {})
        amenity = tags.get("amenity", "")
        leisure = tags.get("leisure", "")
        shop = tags.get("shop", "")

        lat = el.get("lat") or el.get("center", {}).get("lat")
        lng = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lng is None:
            continue

        facility = {
            "name": tags.get("name", "名称不明"),
            "lat": lat,
            "lng": lng,
        }

        emergency = tags.get("emergency", "")

        if shop == "convenience":
            categories["convenience"].append(facility)
        elif emergency == "defibrillator":
            categories["aed"].append(facility)
        elif amenity == "drinking_water":
            categories["drinking_water"].append(facility)
        elif amenity in categories:
            categories[amenity].append(facility)
        elif leisure == "park":
            categories["park"].append(facility)

    return categories


CATEGORY_LABELS = {
    "convenience": "コンビニ",
    "toilets": "公衆トイレ",
    "hospital": "病院",
    "clinic": "クリニック",
    "fuel": "ガソリンスタンド",
    "aed": "AED",
    "drinking_water": "給水ポイント",
    "park": "公園（休憩ポイント）",
}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "使い方: facilities.py <ルートGeoJSONファイルパス>"}))
        sys.exit(1)

    geojson_path = sys.argv[1]
    with open(geojson_path, encoding="utf-8") as f:
        geojson = json.load(f)

    coordinates = geojson["features"][0]["geometry"]["coordinates"]
    sampled = sample_route_points(coordinates, interval_m=2000)

    print(f"ルート上の {len(sampled)} 地点で施設を検索中...", file=sys.stderr)

    all_elements = []
    for i, point in enumerate(sampled):
        lng, lat = point[0], point[1]
        print(f"  検索中: {i+1}/{len(sampled)} ({lat:.4f}, {lng:.4f})", file=sys.stderr)
        if i > 0:
            time.sleep(2)  # Overpass APIレート制限対策
        try:
            elements = query_overpass(lat, lng, radius=500)
            all_elements.extend(elements)
        except Exception as e:
            print(f"  警告: 地点 {i+1} の検索失敗: {e}", file=sys.stderr)

    categories = categorize_facilities(all_elements)

    output = {
        "categories": categories,
        "summary": {label: len(categories[key]) for key, label in CATEGORY_LABELS.items()},
    }

    output_path = "/tmp/kitaku_facilities.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 標準出力にサマリーを出す
    result = {"facilities_path": output_path, "summary": output["summary"]}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
