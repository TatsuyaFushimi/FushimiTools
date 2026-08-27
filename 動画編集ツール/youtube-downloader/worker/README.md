# youtube-downloader-gateway（認証ゲートウェイWorker）

Flare Downloaderのチーム共有Web版用の認証ゲートウェイ。Cloudflare Zero Trust Access（Googleログイン制限）を通過したリクエストのみを、Render.com上の実バックエンド（Flaskアプリ）へ中継する。

## 役割

1. Cloudflare Accessが認証済みリクエストに付与する `Cf-Access-Authenticated-User-Email` ヘッダーを読み取る（ヘッダーが無い場合は500エラーを返す）
   - このヘッダーは万一Access Application側の保護範囲設定に不備があった場合に偽装されうるため、単独では信頼しない。同時に付与される `Cf-Access-Jwt-Assertion` ヘッダー（Access発行のJWT）の署名・issuer・audienceを検証し、失敗時は401を返す
2. リクエスト（メソッド・パス・クエリ・ボディ・ヘッダー）をRenderの実バックエンドへそのまま転送する
3. 転送時に以下のヘッダーを追加する
   - `X-User-Email`: Accessから取得したメールアドレス
   - `X-Worker-Secret`: Worker側で保持する共有シークレット
4. レスポンス（動画ファイルのダウンロード等のバイナリ含む）はストリーミングでそのまま返す
5. `/health` のみ認証チェックをスキップして200を返す（Render起動確認用。Cloudflare側の疎通確認にも使える）

## セットアップ

```bash
cd worker
npm install
```

## デプロイ

```bash
npx wrangler deploy
```

初回デプロイ後、`https://youtube-downloader-gateway.<アカウント名>.workers.dev` のようなURLが払い出される。

## 環境変数・シークレットの設定

### RENDER_BACKEND_URL（平文・wrangler.jsonc内で管理）

`wrangler.jsonc` の `vars.RENDER_BACKEND_URL` を、Renderへの実デプロイ後に発行される実際のURLに書き換える。

```jsonc
"vars": {
	"RENDER_BACKEND_URL": "https://flare-downloader-xxxx.onrender.com"
}
```

書き換え後は再度 `npx wrangler deploy` が必要。

### CF_ACCESS_TEAM_DOMAIN / CF_ACCESS_AUD（平文・wrangler.jsonc内で管理）

`Cf-Access-Jwt-Assertion` ヘッダーのJWT署名検証に使う。どちらも秘密情報ではないため`wrangler.jsonc`の`vars`にそのまま書ける。

```jsonc
"vars": {
	"CF_ACCESS_TEAM_DOMAIN": "your-team-domain",
	"CF_ACCESS_AUD": "your-aud-tag"
}
```

- `CF_ACCESS_TEAM_DOMAIN`: Cloudflare Zero Trustのteam domain。`https://one.dash.cloudflare.com/` の左メニュー「Settings」→「Custom Pages」等で確認できる `<team-domain>.cloudflareaccess.com` の `<team-domain>` 部分
- `CF_ACCESS_AUD`: このWorker用に作成したAccess Applicationの「Application Audience (AUD) Tag」。`Access` → `Applications` で対象アプリケーションを開き、「Overview」タブに表示される値をコピーする

書き換え後は再度 `npx wrangler deploy` が必要。

### WORKER_SHARED_SECRET（シークレット・コマンドで設定）

Worker⇔Renderバックエンド間だけで共有する秘密の値。ダッシュボードやリポジトリには書かず、コマンドで設定する。

```bash
npx wrangler secret put WORKER_SHARED_SECRET
# プロンプトが出たら任意のランダム文字列を入力（例: openssl rand -hex 32 で生成した値）
```

Render側（Flaskアプリ）にも同じ値を環境変数として設定し、`X-Worker-Secret` ヘッダーの値を検証する実装を入れる想定（Render側の実装はこのWorkerのスコープ外）。

## Cloudflare Zero Trust Access側の設定（ダッシュボード操作）

Worker自体は認証ロジックを持たない。Cloudflare Access側で「このWorkerのURLに来たリクエストはGoogleログイン必須」という制限をかける。YouQR（flare-qr-v2）で同様の設定を行っている場合はそちらを参考にできる。

1. https://one.dash.cloudflare.com/ を開き、対象アカウントを選択する
2. 左メニューの「Access」→「Applications」を開く
3. 右上の「Add an application」をクリックし、「Self-hosted」を選択する
4. アプリケーション設定画面で以下を入力する
   - Application name: 任意（例: `Flare Downloader Gateway`）
   - Session Duration: 任意（例: 24時間）
   - Application domain: このWorkerの `*.workers.dev` のホスト名（例: `youtube-downloader-gateway.<アカウント名>.workers.dev`）を指定する
5. 「Next」をクリックし、Policies設定画面に進む
6. ポリシーを作成する
   - Policy name: 任意（例: `Busoken members only`）
   - Action: `Allow`
   - Include条件で「Login Methods」または「Emails ending in」等を選び、社内ドメインまたは許可するGoogleアカウントを指定する
7. Identity providersでGoogleを選択する（未追加の場合は「Settings」→「Authentication」からGoogle IdPを事前に追加しておく）
8. 「Add application」で保存する
9. 設定後、対象の `*.workers.dev` URLへアクセスするとGoogleログイン画面が挟まり、許可されたアカウントのみ通過できることを確認する

## ローカル動作確認

```bash
npx wrangler dev
```

`.dev.vars` に以下を書くとローカルでのみ有効な環境変数・シークレットとして読み込まれる（Gitにはコミットしない）。

```
RENDER_BACKEND_URL=http://127.0.0.1:適当なポート
WORKER_SHARED_SECRET=任意のテスト用文字列
```

`Cf-Access-Authenticated-User-Email` / `Cf-Access-Jwt-Assertion` ヘッダーはローカルのAccessでは付与されないため、curl等で手動付与して動作確認する。ただし本物のJWTを用意できない場合は署名検証に失敗して401になる（これが正しい挙動）。JWT検証部分のロジック単体を確認したい場合は、テスト用の鍵ペアで自己発行したJWTを使ったスクリプトで検証する。

```bash
curl "http://localhost:8787/api/progress/xxxx" \
  -H "Cf-Access-Authenticated-User-Email: test@example.com" \
  -H "Cf-Access-Jwt-Assertion: <本物のAccess JWT>"
```
