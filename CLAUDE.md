# アプリ化PJ

## プロジェクト概要

要望のツールサイト・アプリをなんでも作るプロジェクト。
ユーザーから「こういう機能が欲しい」という要望を受け取り、実現可能性と対応方法を提示した上で開発する。

### 開発方針

- 共有を前提として作成（Webツール → GitHub Pages）
- 各ツール・アプリはフォルダ分け
- Claude AI が必要かどうかを毎回明示する
- 開発ノウハウは `knowhow.md` に蓄積
- 各フォルダに `service.md` を必ず作成・維持する（利用サービス・動作概要をまとめたもの）

## 役割フロー

```
1. ユーザーが要望を提示
2. 実現可否・対応方法・AI必要性を提示
3. ユーザーが承認
4. 開発 → フォルダに格納
5. index.md と knowhow.md を更新
6. service.md を作成（新規）または更新（仕様変更時）
```

## 技術スタック

| 用途 | 技術 |
|------|------|
| フロントエンド | HTML/CSS/JS（複雑な場合は React/Vue） |
| バックエンド | 未定（必要な場合のみ） |
| AI連携 | Claude API（必要な場合のみ） |
| 共有方法（静的サイト） | GitHub Pages |
| 共有方法（バックエンドあり） | Render.com（無料） |
| 共有方法（アプリ） | 必要になった時点で検討 |

## ディレクトリ構成

```
アプリ化PJ/
├── CLAUDE.md          # このファイル
├── index.md           # ツール一覧・概要
├── knowhow.md         # 開発ノウハウ蓄積
└── [tool-name]/       # ツールごとのフォルダ
    ├── service.md     # ★ 利用サービス・動作概要（必須・仕様変更時に更新）
    ├── README.md
    └── ...
```

## リポジトリ

https://github.com/TatsuyaFushimi/FushimiTools

GitHub Pages URL: https://TatsuyaFushimi.github.io/FushimiTools/（有効化後）

## コマンド

```bash
# 変更をプッシュ
git add . && git commit -m "メッセージ" && git push

# Renderにデプロイ（git pushだけでは自動デプロイされないため手動実行が必要）
render deploys create srv-d8l3bt9o3t8c73ajjgig --confirm
```

## Renderサービス

| ツール | サービスID | URL |
|--------|-----------|-----|
| Flare Downloader | srv-d8l3bt9o3t8c73ajjgig | https://fushimitools-youtube.onrender.com |
| QR Generator | srv-d8l6vem7r5hc739n7ci0 | https://flareqr.onrender.com |
