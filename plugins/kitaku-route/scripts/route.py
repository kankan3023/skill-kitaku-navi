#!/usr/bin/env python3
"""OSRMを使った徒歩ルート計算"""

import json
import sys
import urllib.request


def get_route(origin_lng: float, origin_lat: float, dest_lng: float, dest_lat: float) -> dict:
    """OSRMで徒歩ルートを取得する"""
    url = (
        f"https://router.project-osrm.org/route/v1/foot/"
        f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        f"?overview=full&geometries=geojson&steps=true"
    )

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data["code"] != "Ok":
        return {"error": f"ルート計算に失敗しました: {data.get('message', 'unknown error')}"}

    route = data["routes"][0]
    distance_km = round(route["distance"] / 1000, 1)
    duration_min = round(route["duration"] / 60)
    # 徒歩4km/hで再計算（OSRMの推定より保守的に）
    walking_hours = round(distance_km / 4, 1)

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": route["geometry"],
                "properties": {
                    "distance_km": distance_km,
                    "duration_min": duration_min,
                    "walking_hours": walking_hours,
                },
            }
        ],
    }

    # GeoJSONファイルに保存
    output_path = "/tmp/kitaku_route.geojson"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    return {
        "distance_km": distance_km,
        "duration_min": duration_min,
        "walking_hours": walking_hours,
        "geojson_path": output_path,
        "coordinates_count": len(route["geometry"]["coordinates"]),
    }


def main():
    if len(sys.argv) != 5:
        print(json.dumps({"error": "使い方: route.py <出発lng> <出発lat> <目的lng> <目的lat>"}))
        sys.exit(1)

    origin_lng, origin_lat, dest_lng, dest_lat = map(float, sys.argv[1:5])
    result = get_route(origin_lng, origin_lat, dest_lng, dest_lat)

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
