# Flare Downloader（チーム共有Web版）バックエンド

Cloudflare Worker（Cloudflare Access認証済みユーザーのリクエストを転送するリバースプロキシ）の
後段に配置する想定のFlaskサーバー。Render.comにDockerfileベースでデプロイする。

デスクトップアプリ版（`../app.py`）とは完全に独立しており、このディレクトリ配下のみで完結する。

## 前提: Workerからのヘッダー

このサーバーは単体で外部公開しない前提。Workerが以下2つのヘッダーを付けて転送してくる。

- `X-Worker-Secret`: 環境変数 `WORKER_SHARED_SECRET` と一致しないリクエストは403で拒否する
- `X-User-Email`: Cloudflare Access認証済みユーザーのメールアドレス（Cookie分離・スプレッドシートログに使用）

## ローカルでの動作確認

```bash
cd "動画編集ツール/youtube-downloader/server"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# ffmpegが無ければ入れる（macOSの場合）
brew install ffmpeg

export WORKER_SHARED_SECRET="local-test-secret"
# Googleスプレッドシートログを試す場合（無くてもダウンロード自体は動く）
# export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat /path/to/service-account.json)"

python3 app.py
# → http://localhost:5000
```

### 動作確認コマンド例

```bash
# 構文チェック
python3 -m py_compile app.py

# ヘッダー無し → 403になることを確認
curl -i -X POST http://localhost:5000/api/info \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://youtu.be/uvNdL7D_Fd4"}'

# 正しいヘッダー付き → 動画情報が取れることを確認
curl -s -X POST http://localhost:5000/api/info \
  -H "X-Worker-Secret: local-test-secret" \
  -H "X-User-Email: test@example.com" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://youtu.be/uvNdL7D_Fd4"}'
```

`/`（`http://localhost:5000/`）をブラウザで開けば簡易UIからも試せる（Workerを経由しないローカル確認では
ブラウザからのリクエストにヘッダーが付かないため403になる。ヘッダー検証込みで確認したい場合は上記curl、
またはヘッダー検証をローカルでは一時的に外す等で対応する）。

## Renderへのデプロイ

DockerfileベースのWeb Serviceとして作成する。

1. Render Dashboard → New → Web Service
2. リポジトリ・ブランチを選択し、Root Directory に `動画編集ツール/youtube-downloader/server` を指定
3. Environment に `Docker` を選択（Dockerfileが自動検出される）
4. 環境変数を設定
   - `WORKER_SHARED_SECRET`: Worker側と一致する共有シークレット
   - `GOOGLE_SERVICE_ACCOUNT_JSON`: サービスアカウントのJSON鍵の中身をそのまま貼り付け
   - `PORT`: Renderが自動で設定するため通常は指定不要（Dockerfileが `$PORT` を読む）
5. デプロイ後、WorkerのオリジンURLをこのRenderサービスのURLに向ける

## 注意事項

- `jobs` 辞書・ダウンロード枠のsemaphoreをインメモリで保持する設計のため、**プロセスは1つで起動すること**
  （Dockerfileで `gunicorn --workers 1 --threads 8` に固定済み。ワーカー数を増やすとプロセス間で状態が
  共有されず、進捗ポーリングや同時実行数の制御が壊れる）
- ダウンロード枠は合計2。1080p以下は1枠消費（最大2本同時）、4K(2160p以上)を含む場合は2枠消費
  （4Kのダウンロード中は他のジョブが待機する）
- 一時ファイルは `/tmp` 配下に `ytdl_job_{job_id}_...` というディレクトリ名で作成され、
  ダウンロード完了後のファイル取得時・失敗時に削除される。取得されないまま残ったディレクトリは
  10分ごとのバックグラウンド処理で（完了/失敗から30分経過したものを）掃除する
- 個人のCookieファイルは `/tmp/yt_cookies_{user_idハッシュ}.txt` としてユーザーごとに分離される
