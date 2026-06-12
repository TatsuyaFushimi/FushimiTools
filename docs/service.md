# Fushimi Tools ポータル — サービス構成・動作概要

## 何をするサイトか

社内ツール・アプリの一覧ポータルサイト。
各ツールへのリンクとダウンロードページをまとめている。

---

## 利用サービス一覧

| サービス | 役割 | 備考 |
|---------|------|------|
| **GitHub Pages** | 静的サイトのホスティング | `docs/` フォルダの内容がそのまま公開される |
| **GitHub** | ソースコード管理・Pages配信 | pushするだけで自動反映 |

バックエンドなし。外部APIなし。完全静的サイト。

---

## 動作フロー

```
git push
  → GitHub が docs/ フォルダを検出
  → GitHub Pages として自動デプロイ
  → https://TatsuyaFushimi.github.io/FushimiTools/ で公開
```

---

## ファイル構成

| ファイル | 内容 |
|---------|------|
| `index.html` | トップページ（ツール一覧） |
| `flare-downloader.html` | Flare Downloaderのダウンロード＆セットアップ案内 |
| `fushimi-tools-icon.png` | サイトfaviconおよびブランドアイコン |
| `flare-icon.png` | Flare Downloaderのアイコン |

---

## 掲載ツール一覧

| ツール名 | リンク先 | 種別 |
|---------|---------|------|
| Flare Downloader | flare-downloader.html（配布ページ） | macOS .app |
| Flare QR | https://flareqr.onrender.com | Webアプリ（Render） |
