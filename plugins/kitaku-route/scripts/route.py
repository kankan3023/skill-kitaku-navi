#!/usr/bin/env python3
"""OSRMを使った徒歩ルート計算"""

import json
import sys
import urllib.request


MODIFIER_LABELS = {
    "left": "左折",
    "right": "右折",
    "slight left": "やや左へ",
    "slight right": "やや右へ",
    "sharp left": "大きく左折",
    "sharp right": "大きく右折",
    "straight": "直進",
    "uturn": "Uターン",
}

MANEUVER_LABELS = {
    "turn": None,  # modifier で決まる
    "new name": "道なりに進む",
    "depart": "出発",
    "continue": None,  # modifier で決まる
    "merge": "道なりに合流",
    "fork": None,  # modifier で決まる
    "roundabout": "ロータリーを通過",
    "end of road": None,  # modifier で決まる
}


def _build_instruction(maneuver: dict, street: str) -> str:
    """OSRM maneuver から日本語の案内文を生成する"""
    m_type = maneuver.get("type", "")
    modifier = maneuver.get("modifier", "")

    label = MANEUVER_LABELS.get(m_type)
    if label is None:
        # modifier から動作を決定
        action = MODIFIER_LABELS.get(modifier, "進む")
    else:
        action = label

    if street:
        return f"「{street}」を{action}"
    return action


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

    # ステップ情報を抽出
    steps = []
    cumulative_m = 0
    for step in route["legs"][0]["steps"]:
        maneuver = step.get("maneuver", {})
        m_type = maneuver.get("type", "")
        # arrive(到着)は最後に追加するので一旦スキップ
        if m_type == "arrive":
            continue
        distance_m = round(step.get("distance", 0))
        cumulative_m += distance_m
        steps.append({
            "instruction": _build_instruction(maneuver, step.get("name", "")),
            "street": step.get("name", ""),
            "distance_m": distance_m,
            "cumulative_m": cumulative_m,
            "location": maneuver.get("location"),
        })
    # 到着ステップ
    steps.append({
        "instruction": "目的地に到着",
        "street": "",
        "distance_m": 0,
        "cumulative_m": cumulative_m,
        "location": route["legs"][0]["steps"][-1]["maneuver"]["location"],
    })

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
                    "steps": steps,
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
