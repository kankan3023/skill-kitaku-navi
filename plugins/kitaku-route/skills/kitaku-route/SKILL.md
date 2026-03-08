---
name: kitaku-route
description: >
  災害時の徒歩帰宅ルートを生成するスキル。出発地と目的地から安全な徒歩ルートを計算し、
  ルート沿いの避難所・給水拠点・コンビニ・AED・トイレ等の防災情報を自動収集して、
  紙で持てるPDFマニュアルを出力する。「帰宅ルート」「災害」「徒歩で帰る」「帰宅難民」
  などのキーワードで自動起動。
user-invocable: true
argument-hint: "[出発地] [目的地]"
---

# 災害時帰宅ルート生成スキル

あなたは災害時の徒歩帰宅を支援するAIエージェントです。
ユーザーの出発地と目的地から、安全な徒歩帰宅ルートを生成し、
ルート沿いの防災情報を自動収集して、紙で持てるPDFマニュアルを作成します。

## 事前準備

初回実行時、依存パッケージをインストールする。

```bash
pip install -r ${CLAUDE_PLUGIN_ROOT}/requirements.txt
```

## 処理フロー

以下の手順を**自律的に**実行してください。各ステップの結果をユーザーに報告しながら進めること。

### Step 1: 出発地・目的地の確認

- 引数があればそれを使う: `$ARGUMENTS`
- 引数がなければユーザーに出発地と目的地を聞く
- 住所でも駅名でもランドマーク名でもOK

### Step 2: ジオコーディング（住所→座標変換）

国土地理院APIを使って座標に変換する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/geocode.py "出発地の住所"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/geocode.py "目的地の住所"
```

結果は `{"lat": ..., "lng": ..., "label": "..."}` のJSON形式で返る。
座標が取得できなかった場合は、ユーザーにより具体的な住所を聞き直す。

### Step 3: 徒歩ルート計算

OSRMを使って徒歩ルートを取得する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/route.py <出発lng> <出発lat> <目的lng> <目的lat>
```

結果として以下の情報が得られる:
- 総距離（km）
- 推定所要時間（徒歩 4km/h で計算）
- ルートの座標列（GeoJSON: `/tmp/kitaku_route.geojson`）
- ターンバイターン案内（通り名・曲がる方向）

### Step 4: ルート沿いの施設情報取得

Overpass APIを使って、ルート沿いの防災関連施設を検索する。
**注意: Overpass APIにはレート制限があるため、このステップには数十秒かかる。**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/facilities.py /tmp/kitaku_route.geojson
```

取得する施設:
- コンビニ（帰宅支援ステーション候補）
- 公衆トイレ
- 病院・クリニック
- AED（自動体外式除細動器）
- 給水ポイント
- 公園（休憩ポイント）
- ガソリンスタンド（帰宅支援ステーション候補）

結果: `/tmp/kitaku_facilities.json`

### Step 5: 避難場所データ取得

東京都オープンデータから避難場所一覧を取得し、ルート沿いの避難場所を抽出する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/shelters.py /tmp/kitaku_route.geojson
```

結果: `/tmp/kitaku_shelters.json`
- ルートから500m以内の避難場所一覧
- 各避難場所の対応災害種別（洪水・地震・津波等）

### Step 6: 地図画像生成

ルートを区間分割し、施設・避難場所マーカー付きの拡大地図を生成する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/map_image.py \
  /tmp/kitaku_route.geojson \
  /tmp/kitaku_facilities.json \
  /tmp/kitaku_maps \
  /tmp/kitaku_shelters.json
```

- 第3引数は出力ディレクトリ（自動作成される）
- ルートを約2km区間に分割し、統一縮尺で地図を生成
- 結果: `/tmp/kitaku_maps/map_segment_1.png`, `map_segment_2.png`, ...

### Step 7: PDF生成

すべての情報をまとめてPDFを生成する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_pdf.py \
  --route /tmp/kitaku_route.geojson \
  --facilities /tmp/kitaku_facilities.json \
  --shelters /tmp/kitaku_shelters.json \
  --map /tmp/kitaku_maps \
  --origin "出発地名" \
  --destination "目的地名" \
  --output <出力PDFパス>
```

出力先はユーザーのカレントディレクトリに `帰宅ルート_YYYYMMDD.pdf` とする。

PDFの内容:
- 表紙（出発地・目的地・距離・所要時間・施設サマリー）
- 帰宅前の準備（必要水分量・持ち物チェックリスト・地図凡例）
- 区間地図ページ（拡大地図 + ターンバイターン案内）
- 避難場所一覧（対応災害種別付き）
- 緊急連絡先・徒歩帰宅の心得
- 出典・ライセンス表記

### Step 8: 結果報告

ユーザーに以下を報告する:
- 総距離と推定所要時間
- 発見した施設の概要（コンビニ○件、トイレ○件、避難場所○件 等）
- PDFの出力先パス
- 「このPDFを印刷して持ち歩くことをおすすめします」と伝える

## 注意事項

- すべてのAPIはキー不要。ネットワーク接続は必要。
- 対象地域は主に東京都内だが、OSRMとOverpassは全国対応。
- OSRMの公開デモサーバーはレート制限があるため、連続リクエストは避ける。
- Overpass APIも連続リクエストで429エラーが出る場合がある（スクリプト内で2秒間隔に制御済み）。
- エラーが発生した場合は、ユーザーにわかりやすく状況を説明し、代替案を提示する。
- PDFの出典表記は自動的に含まれる。

## 地図マーカーの凡例

| マーカー | 対象 |
|----------|------|
| 緑★ | 出発地 |
| 赤★ | 目的地 |
| 黄▲ | 避難場所 |
| 橙■ | コンビニ |
| 青● | 公衆トイレ |
| 桃＋ | AED |
| 紫◆ | 病院・クリニック |
