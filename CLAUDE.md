# アプリ化PJ

## プロジェクト概要

要望のツールサイト・アプリをなんでも作るプロジェクト。
ユーザーから「こういう機能が欲しい」という要望を受け取り、実現可能性と対応方法を提示した上で開発する。

### 開発方針

- 共有を前提として作成（Webツール → GitHub Pages）
- 各ツール・アプリはフォルダ分け
- Claude AI が必要かどうかを毎回明示する
- 開発ノウハウは `knowhow.md` に蓄積

## 役割フロー

```
1. ユーザーが要望を提示
2. 実現可否・対応方法・AI必要性を提示
3. ユーザーが承認
4. 開発 → フォルダに格納
5. index.md と knowhow.md を更新
```

## 技術スタック

| 用途 | 技術 |
|------|------|
| フロントエンド | HTML/CSS/JS（複雑な場合は React/Vue） |
| バックエンド | 未定（必要な場合のみ） |
| AI連携 | Claude API（必要な場合のみ） |
| 共有方法（Web） | GitHub Pages |
| 共有方法（アプリ） | 必要になった時点で検討 |

## ディレクトリ構成

```
アプリ化PJ/
├── CLAUDE.md          # このファイル
├── index.md           # ツール一覧・概要
├── knowhow.md         # 開発ノウハウ蓄積
└── [tool-name]/       # ツールごとのフォルダ
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
```
