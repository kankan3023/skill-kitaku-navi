#!/usr/bin/env python3
"""ジオコーディング（住所・駅名・ランドマーク→座標変換）
国土地理院APIをメインに、Nominatim（OSM）をフォールバックとして使用。
"""

import json
import sys
import urllib.request
import urllib.parse


def geocode_gsi(query: str) -> dict | None:
    """国土地理院APIで検索（住所に強い）"""
    encoded = urllib.parse.quote(query)
    url = f"https://msearch.gsi.go.jp/address-search/AddressSearch?q={encoded}"

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if not data:
        return None

    result = data[0]
    coordinates = result["geometry"]["coordinates"]
    label = result["properties"]["title"]

    # 東京都のクエリなのに東京都以外が返ってきた場合はスキップ
    if "東京" in query and "東京都" not in label:
        # 東京都の結果を探す
        for r in data:
            if "東京都" in r["properties"]["title"]:
                coordinates = r["geometry"]["coordinates"]
                label = r["properties"]["title"]
                break
        else:
            return None

    return {"lat": coordinates[1], "lng": coordinates[0], "label": label}


def geocode_nominatim(query: str) -> dict | None:
    """Nominatim（OSM）で検索（駅名・ランドマークに強い）"""
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "limit": 5,
        "countrycodes": "jp",
        "accept-language": "ja",
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": "kitaku-route-skill/0.1"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if not data:
        return None

    # 東京都の結果を優先
    for result in data:
        if "東京" in result.get("display_name", ""):
            return {
                "lat": float(result["lat"]),
                "lng": float(result["lon"]),
                "label": result["display_name"].split(",")[0],
            }

    # 東京都の結果がなければ最初の結果を使用
    result = data[0]
    return {
        "lat": float(result["lat"]),
        "lng": float(result["lon"]),
        "label": result["display_name"].split(",")[0],
    }


def geocode(query: str) -> dict | None:
    """住所・駅名・ランドマーク名から座標を取得する（2段階フォールバック）"""
    # 駅名・ランドマーク系のクエリはNominatimを優先
    landmark_keywords = ["駅", "空港", "公園", "タワー", "ビル", "大学", "学校", "神社", "寺"]
    is_landmark = any(kw in query for kw in landmark_keywords)

    if is_landmark:
        result = geocode_nominatim(query)
        if result:
            return result

    # 住所系は国土地理院を優先
    result = geocode_gsi(query)
    if result:
        return result

    # フォールバック
    if not is_landmark:
        result = geocode_nominatim(query)
        if result:
            return result

    return None


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "使い方: geocode.py <住所または場所名>"}))
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    result = geocode(query)

    if result is None:
        print(json.dumps({"error": f"'{query}' の座標が見つかりませんでした"}, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
