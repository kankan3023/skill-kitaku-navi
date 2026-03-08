# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AGI Lab AI Agent ハッカソン提出作品。災害時の徒歩帰宅ルートを生成し、PDF出力する Claude Code スキル。
対象地域は東京都内。APIキー不要のサービスのみ使用。

設計ドキュメント: `KITAKU-ROUTE-DESIGN.md` を必ず参照すること。

## Architecture

Claude Code スキル（SKILL.md ベース）として実装。

### データフロー
1. ユーザーから出発地・目的地をヒアリング
2. 国土地理院 API でジオコーディング（住所→座標）
3. OSRM で徒歩ルート計算
4. ルート座標列から通過自治体を特定（逆ジオコーディング）
5. 各自治体の防災情報を自動収集（避難所・AED・給水拠点・トイレ等）
6. ルートから一定距離内の施設を抽出
7. 自治体ごとにセクション分けしてPDF出力

### 外部API（全てAPIキー不要）
- **国土地理院**: ジオコーディング、地図タイル
- **OSRM公開デモサーバー**: 徒歩ルート計算
- **Overpass API**: OSMデータ検索（コンビニ・トイレ等）
- **東京都オープンデータ**: 避難所・給水拠点CSV
- **AEDオープンデータAPI**: 最寄りAED検索
- **ハザードマップポータル**: 洪水・土砂災害タイル

### 技術スタック
- Python（folium/staticmap で地図画像生成）
- PDF生成ライブラリ
- 自治体標準オープンデータセット（デジタル庁共通フォーマット）

## Development Guidelines

- 「最短ルート」ではなく「最安全ルート」＋「帰宅支援情報付き」がコンセプト
- スマホが使えない状況を想定し、紙（PDF）で持てる価値を重視
- PDFには出典・ライセンス表記を必ず含めること（詳細は KITAKU-ROUTE-DESIGN.md 参照）
- 「スキルは育てるもの」：最小構成（Step 1）から段階的に機能追加
