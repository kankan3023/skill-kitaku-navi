#!/usr/bin/env python3
"""帰宅ルート情報をPDFにまとめる"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime

try:
    from fpdf import FPDF
except ImportError:
    print("fpdf2がインストールされていません。以下を実行してください:", file=sys.stderr)
    print("  pip install fpdf2", file=sys.stderr)
    sys.exit(1)


LEGEND_ITEMS = [
    ("緑★", "出発地"),
    ("赤★", "目的地"),
    ("黄▲", "避難場所"),
    ("橙■", "コンビニ（帰宅支援ステーション）"),
    ("青●", "公衆トイレ"),
    ("桃＋", "AED（自動体外式除細動器）"),
    ("紫◆", "病院・クリニック"),
]


class KitakuPDF(FPDF):
    def __init__(self):
        super().__init__()
        self._setup_font()

    def _setup_font(self):
        """日本語フォントの設定（Noto Sans JP TTF）"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bundled_font = os.path.join(script_dir, "..", "fonts", "NotoSansJP-Variable.ttf")

        if os.path.exists(bundled_font):
            self.add_font("NotoSansJP", "", bundled_font)
            self.font_name = "NotoSansJP"
            return

        print("警告: 日本語フォントが見つかりません。fonts/NotoSansJP-Variable.ttf を配置してください。", file=sys.stderr)
        self.font_name = "Helvetica"

    def header(self):
        self.set_font(self.font_name, "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 5, "災害時徒歩帰宅ルートマニュアル", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_name, "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"- {self.page_no()} -", align="C")


def generate_pdf(route_path: str, facilities_path: str, map_dir: str,
                 origin: str, destination: str, output_path: str,
                 shelters_path: str = None):
    """PDFを生成する"""
    with open(route_path, encoding="utf-8") as f:
        route_data = json.load(f)

    props = route_data["features"][0]["properties"]
    distance_km = props["distance_km"]
    walking_hours = props["walking_hours"]

    facilities = None
    if facilities_path and os.path.exists(facilities_path):
        with open(facilities_path, encoding="utf-8") as f:
            facilities = json.load(f)

    shelters = None
    if shelters_path and os.path.exists(shelters_path):
        with open(shelters_path, encoding="utf-8") as f:
            shelters = json.load(f)

    # 地図画像の収集（ディレクトリなら中の画像を、ファイルならそれ1つを使う）
    map_images = []
    if map_dir:
        if os.path.isdir(map_dir):
            map_images = sorted(glob.glob(os.path.join(map_dir, "map_segment_*.png")))
        elif os.path.isfile(map_dir):
            map_images = [map_dir]

    today = datetime.now().strftime("%Y年%m月%d日")

    pdf = KitakuPDF()
    font = pdf.font_name

    # === 表紙 ===
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font(font, "", 24)
    pdf.cell(0, 15, "災害時 徒歩帰宅ルート", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 15, "マニュアル", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(15)

    pdf.set_font(font, "", 14)
    pdf.cell(0, 10, f"出発地: {origin}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"目的地: {destination}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.cell(0, 10, f"総距離: {distance_km} km", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"推定所要時間: 約 {walking_hours} 時間（徒歩4km/h）", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf.set_font(font, "", 10)
    pdf.cell(0, 8, f"作成日: {today}", align="C", new_x="LMARGIN", new_y="NEXT")

    # 施設サマリーを表紙に
    if facilities:
        pdf.ln(10)
        pdf.set_font(font, "", 11)
        summary = facilities.get("summary", {})
        shelter_count = shelters.get("nearby_count", 0) if shelters else 0
        items = list(summary.items())
        if shelter_count:
            items.append(("避難場所", shelter_count))
        for label, count in items:
            pdf.cell(0, 7, f"{label}: {count} 件", align="C", new_x="LMARGIN", new_y="NEXT")

    # === 概要・準備ページ ===
    pdf.add_page()
    pdf.set_font(font, "", 18)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 12, "帰宅前の準備", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    water_ml = int(distance_km / 4 * 500)
    pdf.set_font(font, "", 12)
    pdf.cell(0, 8, f"必要な水分量（目安）: 約 {water_ml}ml（{water_ml // 500} 本 x 500ml）", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"推定休憩回数: 約 {max(1, int(walking_hours))} 回（1時間ごと）", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font(font, "", 14)
    pdf.cell(0, 10, "持ち物チェックリスト", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font, "", 11)
    checklist = [
        "[ ] 飲料水（上記目安量）",
        "[ ] 携帯食（チョコ・飴・栄養バー等）",
        "[ ] 携帯電話・モバイルバッテリー",
        "[ ] 現金（小銭含む）",
        "[ ] 身分証明書・健康保険証",
        "[ ] 常備薬",
        "[ ] 懐中電灯（夜間移動の場合）",
        "[ ] 雨具（折りたたみ傘・カッパ）",
        "[ ] このマニュアル（印刷済み）",
        "[ ] 歩きやすい靴",
    ]
    for item in checklist:
        pdf.cell(0, 7, f"  {item}", new_x="LMARGIN", new_y="NEXT")

    # 凡例
    pdf.ln(8)
    pdf.set_font(font, "", 14)
    pdf.cell(0, 10, "地図の凡例", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font, "", 10)
    for symbol, desc in LEGEND_ITEMS:
        pdf.cell(0, 6, f"  {symbol}  {desc}", new_x="LMARGIN", new_y="NEXT")

    # === 区間地図ページ ===
    if map_images:
        for i, img_path in enumerate(map_images):
            pdf.add_page()
            pdf.set_font(font, "", 16)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 10, f"区間 {i + 1} / {len(map_images)}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            pdf.image(img_path, x=10, w=190)
    else:
        pdf.add_page()
        pdf.set_font(font, "", 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, "（地図画像が生成されていません）", new_x="LMARGIN", new_y="NEXT")

    # === 避難場所ページ ===
    if shelters and shelters.get("shelters"):
        pdf.add_page()
        pdf.set_font(font, "", 18)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 12, "ルート沿いの避難場所", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        pdf.set_font(font, "", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 7, "出典: 東京都オープンデータ 避難場所一覧（CC BY 4.0）", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        pdf.set_text_color(0, 0, 0)
        for shelter in shelters["shelters"][:30]:
            name = shelter.get("name", "名称不明")
            addr = shelter.get("address", "")
            dist = shelter.get("distance_m", "?")
            dtypes = shelter.get("disaster_types", [])
            dtype_str = "、".join(dtypes) if dtypes else "指定なし"

            pdf.set_font(font, "", 11)
            pdf.cell(0, 7, f"■ {name}（ルートから約{dist}m）", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font, "", 9)
            pdf.cell(0, 6, f"    {addr}  |  対応災害: {dtype_str}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        if len(shelters["shelters"]) > 30:
            pdf.set_font(font, "", 10)
            pdf.cell(0, 7, f"  ... 他 {len(shelters['shelters']) - 30} 件", new_x="LMARGIN", new_y="NEXT")

    # === 巻末: 緊急情報 ===
    pdf.add_page()
    pdf.set_font(font, "", 18)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 12, "緊急連絡先・お役立ち情報", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font(font, "", 12)
    emergency_info = [
        "【緊急通報】",
        "  警察: 110 / 消防・救急: 119",
        "",
        "【災害用伝言ダイヤル】",
        "  171 に電話 → ガイダンスに従い録音/再生",
        "  ・録音: 171 → 1 → 自宅の電話番号",
        "  ・再生: 171 → 2 → 自宅の電話番号",
        "",
        "【災害用伝言板（web171）】",
        "  https://www.web171.jp/",
        "",
        "【徒歩帰宅の心得】",
        "  ・無理をせず、こまめに休憩を取る",
        "  ・水分補給を忘れない（目安: 1時間あたり500ml）",
        "  ・帰宅支援ステーション（コンビニ等）で水・トイレ・情報を確認",
        "  ・余震に注意し、建物の倒壊やガラス落下に気をつける",
        "  ・夜間の徒歩移動は避け、無理なら一時滞在施設で待機",
    ]
    for line in emergency_info:
        pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")

    # === 出典 ===
    pdf.ln(10)
    pdf.set_font(font, "", 8)
    pdf.set_text_color(100, 100, 100)
    credits = [
        "【出典・ライセンス】",
        "・地図データ: © OpenStreetMap contributors (ODbL)",
        "・地図タイル: 国土地理院 (https://maps.gsi.go.jp/development/ichiran.html)",
        "・ルート計算: OSRM (Open Source Routing Machine)",
        "・施設データ: OpenStreetMap Overpass API",
        "・避難場所データ: 東京都オープンデータ (CC BY 4.0)",
    ]
    for line in credits:
        pdf.cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")

    pdf.output(output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="帰宅ルートPDF生成")
    parser.add_argument("--route", required=True, help="ルートGeoJSONファイル")
    parser.add_argument("--facilities", default=None, help="施設JSONファイル")
    parser.add_argument("--shelters", default=None, help="避難場所JSONファイル")
    parser.add_argument("--map", default=None, help="地図画像ディレクトリまたはファイル")
    parser.add_argument("--origin", required=True, help="出発地名")
    parser.add_argument("--destination", required=True, help="目的地名")
    parser.add_argument("--output", required=True, help="出力PDFパス")

    args = parser.parse_args()
    result = generate_pdf(args.route, args.facilities, args.map, args.origin, args.destination, args.output,
                          shelters_path=args.shelters)
    print(json.dumps({"pdf_path": result}))


if __name__ == "__main__":
    main()
