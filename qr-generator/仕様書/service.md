# Flare QR — サービス構成・動作概要

## 何をするツールか

動的QRコードの生成・管理ツール。QRコードを発行した後でも遷移先URLを変更できる。

---

## 利用サービス一覧

| サービス | 役割 | 備考 |
|---------|------|------|
| **Render.com** | FlaskアプリのホスティングおよびWeb UI・API提供 | 無料プラン（15分無操作でスリープ） |
| **Supabase** | QRコードデータの保存（PostgreSQL） | RLS無効、anonキーでアクセス |
| **Cloudflare Workers** | QRスキャン時のリダイレクト処理 | 常時稼働・無料 |
| **Google Sheets** | QR作成ログの記録 | gspreadとサービスアカウントで書き込み |
| **GitHub** | ソースコード管理・Renderへのデプロイトリガー | pushでRenderが自動デプロイ（要手動トリガー） |

---

## 動作フロー

### QR作成
```
ユーザーがフォームを送信
  → Flask /api/create
  → Supabase に {id, ch名, タイトル, destination_url, password_hash, creator} を保存
  → QR画像生成（遷移先URL = https://redirect.flare-qr.workers.dev/r/<id>）
  → Google Sheetsにログ記録
  → QR画像(Base64)をブラウザに返す
```

### QRスキャン時（リダイレクト）
```
スマホでQRをスキャン
  → Cloudflare Workers (redirect.flare-qr.workers.dev/r/<id>)
  → Supabase REST APIでdestination_urlを検索
  → 302リダイレクト
  ※ RenderがスリープしていてもCloudflareが直接Supabaseを叩くため影響なし
```

### URL変更（編集）
```
ユーザーがパスワード＋新URLを送信
  → Flask /api/edit
  → bcryptでパスワード検証
  → Supabase の destination_url を更新
  → 既存のQRコード（画像）はそのまま使える
```

### QR一覧表示
```
ページ読み込み時 → Flask /api/list → Supabaseから全件取得
ブラウザ側でqrious.jsを使いQR画像をクライアント生成（サーバー不要）
ページネーション10件/ページ、列/ブロック表示切り替え対応
```

---

## インフラ構成図

```
[ブラウザ]
    │
    ├─ Web UI / API ──→ [Render: Flask]
    │                        │
    │                        └─ 読み書き ──→ [Supabase: qr_codes テーブル]
    │                        └─ ログ ─────→ [Google Sheets]
    │
    └─ QRスキャン ───→ [Cloudflare Workers]
                             │
                             └─ destination_url取得 ──→ [Supabase]
```

---

## 主要ファイル

| ファイル | 内容 |
|---------|------|
| `app.py` | Flaskアプリ本体。API全エンドポイント |
| `templates/index.html` | Web UIのフロントエンド（HTML/CSS/JS） |
| `requirements.txt` | Python依存パッケージ |
| `render.yaml` | Renderデプロイ設定 |

---

## 環境変数（Render）

| 変数名 | 内容 |
|-------|------|
| `SUPABASE_URL` | SupabaseプロジェクトURL |
| `SUPABASE_KEY` | Supabase anonキー |
| `APP_URL` | `https://redirect.flare-qr.workers.dev`（Cloudflare Worker URL） |
| `GSHEET_ID` | Google SheetsのスプレッドシートID |
| `GSHEET_CREDS_B64` | サービスアカウントJSONのBase64エンコード |
