#!/usr/bin/env python3
"""ルートと施設を地図上にプロットした静的画像を生成する（区間分割・縮尺統一・図形マーカー対応）"""

import json
import math
import os
import sys

try:
    import staticmap
except ImportError:
    print("staticmapがインストールされていません: pip install staticmap", file=sys.stderr)
    sys.exit(1)

from PIL import ImageDraw

TILE_URL = "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png"
MAP_WIDTH = 800
MAP_HEIGHT = 1000

# 表示するカテゴリ（重要度順）と描画設定
# shape: star, triangle, square, circle, cross, diamond
MARKER_STYLES = {
    "shelter":     {"color": "#DDAA00", "outline": "#806600", "shape": "triangle", "size": 12},
    "convenience": {"color": "#FF6600", "outline": "#993D00", "shape": "square",   "size": 9},
    "toilets":     {"color": "#0066FF", "outline": "#003D99", "shape": "circle",   "size": 8},
    "aed":         {"color": "#FF44AA", "outline": "#992266", "shape": "cross",    "size": 10},
    "hospital":    {"color": "#9933CC", "outline": "#5C1F7A", "shape": "diamond",  "size": 9},
    "clinic":      {"color": "#9933CC", "outline": "#5C1F7A", "shape": "diamond",  "size": 9},
    "start":       {"color": "#00BB00", "outline": "#006600", "shape": "star",     "size": 16},
    "end":         {"color": "#EE0000", "outline": "#880000", "shape": "star",     "size": 16},
}

# 地図に表示するカテゴリ（公園・ガソリンスタンド・給水ポイントは除外）
DISPLAY_CATEGORIES = {"convenience", "toilets", "hospital", "clinic", "aed"}


def distance_m(coord1, coord2):
    dlat = (coord2[1] - coord1[1]) * 111_000
    dlng = (coord2[0] - coord1[0]) * 91_000
    return (dlat**2 + dlng**2) ** 0.5


def split_route_segments(coordinates, segment_km=2.0):
    segment_m = segment_km * 1000
    segments = []
    current_segment = [coordinates[0]]
    accumulated = 0.0

    for i in range(1, len(coordinates)):
        dist = distance_m(coordinates[i - 1], coordinates[i])
        accumulated += dist
        current_segment.append(coordinates[i])

        if accumulated >= segment_m and i < len(coordinates) - 1:
            segments.append(current_segment)
            current_segment = [coordinates[i]]
            accumulated = 0.0

    if len(current_segment) > 1:
        segments.append(current_segment)
    elif segments:
        segments[-1].extend(current_segment[1:])

    return segments


def segment_bbox(segment_coords):
    lngs = [c[0] for c in segment_coords]
    lats = [c[1] for c in segment_coords]
    return min(lngs), min(lats), max(lngs), max(lats)


def bbox_span(bbox):
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def calculate_zoom_for_bbox(lng_span, lat_span, width, height):
    if lng_span == 0 and lat_span == 0:
        return 16
    lng_span *= 1.2
    lat_span *= 1.2
    zoom_lng = math.log2(360.0 / lng_span * width / 256) if lng_span > 0 else 18
    zoom_lat = math.log2(180.0 / lat_span * height / 256) if lat_span > 0 else 18
    return int(min(zoom_lng, zoom_lat))


def compute_unified_zoom(segments):
    min_zoom = 18
    for seg in segments:
        bbox = segment_bbox(seg)
        lng_span, lat_span = bbox_span(bbox)
        zoom = calculate_zoom_for_bbox(lng_span, lat_span, MAP_WIDTH, MAP_HEIGHT)
        min_zoom = min(min_zoom, zoom)
    return min_zoom


def segment_center(segment_coords):
    lngs = [c[0] for c in segment_coords]
    lats = [c[1] for c in segment_coords]
    return (min(lngs) + max(lngs)) / 2, (min(lats) + max(lats)) / 2


def is_in_view(lat, lng, center_lng, center_lat, zoom, width, height):
    lng_range = 360.0 / (2 ** zoom) * width / 256
    lat_range = 180.0 / (2 ** zoom) * height / 256
    return (abs(lng - center_lng) <= lng_range / 2 and
            abs(lat - center_lat) <= lat_range / 2)


# === 座標→ピクセル変換 ===

def lnglat_to_pixel(lng, lat, center_lng, center_lat, zoom, width, height):
    """経緯度をピクセル座標に変換する"""
    n = 2.0 ** zoom
    # 中心のピクセル座標
    cx_tile = (center_lng + 180.0) / 360.0 * n
    cy_tile = (1.0 - math.log(math.tan(math.radians(center_lat)) +
               1.0 / math.cos(math.radians(center_lat))) / math.pi) / 2.0 * n
    # 対象のピクセル座標
    px_tile = (lng + 180.0) / 360.0 * n
    py_tile = (1.0 - math.log(math.tan(math.radians(lat)) +
               1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n

    px = (px_tile - cx_tile) * 256 + width / 2
    py = (py_tile - cy_tile) * 256 + height / 2
    return int(px), int(py)


# === 図形描画関数 ===

def draw_star(draw, cx, cy, size, fill, outline):
    """★ 星型"""
    points = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        r = size if i % 2 == 0 else size * 0.4
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=fill, outline=outline)


def draw_triangle(draw, cx, cy, size, fill, outline):
    """▲ 三角"""
    points = [
        (cx, cy - size),
        (cx - size * 0.87, cy + size * 0.5),
        (cx + size * 0.87, cy + size * 0.5),
    ]
    draw.polygon(points, fill=fill, outline=outline)


def draw_square(draw, cx, cy, size, fill, outline):
    """■ 四角"""
    s = size * 0.7
    draw.rectangle([cx - s, cy - s, cx + s, cy + s], fill=fill, outline=outline)


def draw_circle(draw, cx, cy, size, fill, outline):
    """● 丸"""
    r = size * 0.7
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline)


def draw_cross(draw, cx, cy, size, fill, outline):
    """＋ 十字"""
    t = size * 0.3  # 太さ
    s = size * 0.9
    # 縦棒
    draw.rectangle([cx - t, cy - s, cx + t, cy + s], fill=fill, outline=outline)
    # 横棒
    draw.rectangle([cx - s, cy - t, cx + s, cy + t], fill=fill, outline=outline)


def draw_diamond(draw, cx, cy, size, fill, outline):
    """◆ ひし形"""
    s = size * 0.85
    points = [(cx, cy - s), (cx + s * 0.6, cy), (cx, cy + s), (cx - s * 0.6, cy)]
    draw.polygon(points, fill=fill, outline=outline)


SHAPE_DRAWERS = {
    "star": draw_star,
    "triangle": draw_triangle,
    "square": draw_square,
    "circle": draw_circle,
    "cross": draw_cross,
    "diamond": draw_diamond,
}


def draw_marker(draw, cx, cy, style_key):
    """スタイル名に基づいてマーカーを描画"""
    style = MARKER_STYLES[style_key]
    drawer = SHAPE_DRAWERS[style["shape"]]
    drawer(draw, cx, cy, style["size"], style["color"], style["outline"])


# === マーカー情報の収集 ===

def collect_markers(segment_coords, facilities, shelters, segment_index, total_segments,
                    center_lng, center_lat, zoom):
    """表示範囲内のマーカー情報を収集する（描画順: 重要度低→高）"""
    markers = []  # (lat, lng, style_key)

    # 施設（重要度低いものから）
    if facilities:
        for category, items in facilities.get("categories", {}).items():
            if category not in DISPLAY_CATEGORIES:
                continue
            # clinic は hospital と同じスタイル
            style_key = "hospital" if category == "clinic" else category
            for item in items:
                if is_in_view(item["lat"], item["lng"], center_lng, center_lat, zoom, MAP_WIDTH, MAP_HEIGHT):
                    markers.append((item["lat"], item["lng"], style_key))

    # 避難場所
    if shelters:
        for shelter in shelters.get("shelters", []):
            if is_in_view(shelter["lat"], shelter["lng"], center_lng, center_lat, zoom, MAP_WIDTH, MAP_HEIGHT):
                markers.append((shelter["lat"], shelter["lng"], "shelter"))

    # 出発地・目的地（最前面に描画）
    seg_start = segment_coords[0]
    seg_end = segment_coords[-1]
    if segment_index == 0:
        markers.append((seg_start[1], seg_start[0], "start"))
    if segment_index == total_segments - 1:
        markers.append((seg_end[1], seg_end[0], "end"))

    return markers


# === メイン描画 ===

def render_segment_map(segment_coords, all_coords, facilities, shelters,
                       segment_index, total_segments, zoom):
    """1区間の地図を描画（ルートはstaticmap、マーカーはPillow）"""
    m = staticmap.StaticMap(MAP_WIDTH, MAP_HEIGHT, url_template=TILE_URL)

    center_lng, center_lat = segment_center(segment_coords)

    # 全体ルート（薄いグレー）
    m.add_line(staticmap.Line(
        [c[:2] for c in all_coords], color="#CCCCCC", width=2
    ))

    # この区間のルート（青）
    m.add_line(staticmap.Line(
        [c[:2] for c in segment_coords], color="#0055DD", width=5
    ))

    # staticmap でルートだけ描画
    image = m.render(zoom=zoom, center=[center_lng, center_lat])

    # Pillow でマーカーを描画
    draw = ImageDraw.Draw(image)
    markers = collect_markers(segment_coords, facilities, shelters,
                              segment_index, total_segments,
                              center_lng, center_lat, zoom)

    for lat, lng, style_key in markers:
        px, py = lnglat_to_pixel(lng, lat, center_lng, center_lat, zoom, MAP_WIDTH, MAP_HEIGHT)
        if 0 <= px < MAP_WIDTH and 0 <= py < MAP_HEIGHT:
            draw_marker(draw, px, py, style_key)

    return image


def generate_maps(route_path, facilities_path, output_dir,
                  shelters_path=None, segment_km=2.0):
    with open(route_path, encoding="utf-8") as f:
        geojson = json.load(f)

    coordinates = geojson["features"][0]["geometry"]["coordinates"]

    facilities = None
    if facilities_path:
        with open(facilities_path, encoding="utf-8") as f:
            facilities = json.load(f)

    shelters = None
    if shelters_path:
        with open(shelters_path, encoding="utf-8") as f:
            shelters = json.load(f)

    segments = split_route_segments(coordinates, segment_km=segment_km)
    auto_zoom = compute_unified_zoom(segments)
    zoom = max(auto_zoom, 16)
    print(f"統一ズームレベル: {zoom}（{len(segments)} 区間）", file=sys.stderr)

    os.makedirs(output_dir, exist_ok=True)
    image_paths = []

    for i, segment in enumerate(segments):
        path = os.path.join(output_dir, f"map_segment_{i+1}.png")
        image = render_segment_map(
            segment, coordinates, facilities, shelters,
            i, len(segments), zoom
        )
        image.save(path)
        image_paths.append(path)
        print(f"  区間 {i+1}/{len(segments)} の地図を生成: {path}", file=sys.stderr)

    return image_paths


def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "使い方: map_image.py <ルートGeoJSON> <施設JSON> <出力ディレクトリ> [避難場所JSON] [区間km]"}))
        sys.exit(1)

    route_path = sys.argv[1]
    facilities_path = sys.argv[2] if sys.argv[2] != "none" else None
    output_dir = sys.argv[3]
    shelters_path = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "none" else None
    segment_km = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0

    image_paths = generate_maps(route_path, facilities_path, output_dir,
                                shelters_path=shelters_path, segment_km=segment_km)
    print(json.dumps({"image_paths": image_paths, "count": len(image_paths)}))


if __name__ == "__main__":
    main()
