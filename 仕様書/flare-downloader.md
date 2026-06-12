# Flare Downloader — サービス構成・動作概要

## 何をするツールか

YouTubeのURLを貼り付けてMP4でダウンロードするmacOS専用アプリ。
完全ローカル動作のため、外部サービスへのデータ送信なし。

---

## 利用サービス・ライブラリ一覧

| サービス／ライブラリ | 役割 | 備考 |
|-------------------|------|------|
| **yt-dlp** | YouTube動画・音声のダウンロード | PythonライブラリとしてFlaskから呼び出す |
| **ffmpeg** | 動画と音声のマージ・コーデック変換 | Homebrewでインストール。avc1(h264)形式で出力 |
| **Flask** | ローカルWebサーバー | localhost:5001で起動。ブラウザがUIになる |
| **PyInstaller** | Python＋依存物をmacOS .appにバンドル | arm64(Apple Silicon)専用ビルド |
| **GitHub Releases** | .appのzipファイルを配布 | FlareDownloader-arm64.zip |

外部クラウドサービスは一切使用しない。

---

## 動作フロー

### アプリ起動
```
.appをダブルクリック
  → launcher.py が起動
  → Flask（app.py）をバックグラウンドスレッドで起動
  → localhost:5001 へ0.5秒間隔でポーリング（最大240回=120秒）
  → Flaskが応答したらブラウザで http://localhost:5001 を開く
  ※ 初回起動のみmacOSのGatekeeperスキャンでアイコンが跳ねるだけで終わる（正常）
    → 強制終了してもう一度開くと即起動する
```

### 動画情報取得
```
ユーザーがYouTube URLを入力 → 「情報取得」ボタン
  → POST /api/info
  → yt-dlpで動画タイトル・サムネイル・時間・解像度一覧を取得
  → ブラウザに返してUIに表示
  ※ ボット検知エラー時はCookieカードを表示
```

### ダウンロード
```
ユーザーが解像度を選択 → 「ダウンロード」ボタン
  → POST /api/download（バックグラウンドスレッドで処理開始）
  → yt-dlpがavc1(h264)形式を優先して動画＋音声を個別ダウンロード
  → ffmpegで1つのMP4にマージ
  → GET /api/progress/<job_id> でポーリングしてプログレスバー更新
  → 完了後 GET /api/file/<job_id> でブラウザにファイル送信 → tmpディレクトリを削除
```

### Cookie設定（年齢制限・会員限定動画用）
```
ブラウザからNetscape形式のcookies.txtをアップロード
  → POST /api/cookies → /tmp/yt_cookies.txt に保存
  → 以降のyt-dlp実行時にcookiefileオプションで使用
```

---

## ファイル構成

| ファイル | 内容 |
|---------|------|
| `app.py` | Flaskアプリ本体。APIエンドポイント、yt-dlp呼び出し |
| `launcher.py` | .app起動エントリーポイント。Flask起動＋ブラウザ待機ポーリング |
| `templates/index.html` | Web UIのフロントエンド |
| `flare-downloader.spec` | PyInstallerビルド設定 |
| `build.sh` | ビルドスクリプト（venv作成→PyInstaller→zip化） |

---

## ビルド方法

```bash
cd youtube-downloader
bash build.sh
# → dist/Flare Downloader.app が生成される
# → FlareDownloader-arm64.zip を GitHub Releases にアップロード
```

---

## avc1(h264)優先の理由

yt-dlpのデフォルトはVP9/AV1コーデックをダウンロードするが、
QuickTimeおよびAdobe Premiere Proで開けない問題があるため、
`bestvideo[vcodec^=avc1]` を優先フォーマット指定している。
