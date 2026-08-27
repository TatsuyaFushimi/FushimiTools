# Cookie同期スクリプト（cookie-sync）

伏見さんのローカルChromeからYouTube向けCookieを1日1回抽出し、Cloudflare KV（`SHARED_COOKIE_KV`）へpushするスクリプト。
Renderバックエンド（`youtube-downloader-server`）は、Workerがこのkvから読んだCookieを`X-Shared-Cookie`ヘッダーで受け取り、全ユーザー共通のダウンロードに使う。

## セットアップ

```bash
cd "cookie-sync"
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## 環境変数

| 変数名 | 内容 |
|---|---|
| `CF_ACCOUNT_ID` | CloudflareアカウントID |
| `CF_KV_NAMESPACE_ID` | `SHARED_COOKIE_KV` のnamespace ID（`wrangler kv namespace create`で作成したもの） |

## APIトークンの保存

`CF_API_TOKEN`（KVの書き込み権限を持つCloudflare APIトークン）は、`~/Library/LaunchAgents/`配下のplistが
他ローカルユーザーからも読める権限になりがちなため、plistには書かない。代わりに以下のファイルに保存する。

```bash
echo -n "実際のAPIトークン" > ~/.flare_downloader_cf_token
chmod 600 ~/.flare_downloader_cf_token
```

## 手動実行（動作確認）

```bash
CF_ACCOUNT_ID=xxx CF_KV_NAMESPACE_ID=xxx venv/bin/python3 sync_cookie.py
```

初回実行時、ChromeのCookie（暗号化キー）を読むためmacOSのキーチェーンアクセス許可を求められることがある。許可すること。

## launchdへの登録（1日1回自動実行）

1. 上記の手順で `~/.flare_downloader_cf_token` にAPIトークンを保存する
2. `com.busoken.flaredownloader.cookiesync.plist` 内の `CF_ACCOUNT_ID` / `CF_KV_NAMESPACE_ID` を実際の値に書き換える
3. `~/Library/LaunchAgents/` にコピーする

```bash
cp com.busoken.flaredownloader.cookiesync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.busoken.flaredownloader.cookiesync.plist
```

- 実行ログ: `cookiesync.log` / `cookiesync.error.log`（このフォルダ配下に出力される）
- 解除する場合: `launchctl unload ~/Library/LaunchAgents/com.busoken.flaredownloader.cookiesync.plist`
- 設定変更後は unload → load し直すこと
