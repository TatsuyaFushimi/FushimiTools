#!/usr/bin/env python3
"""伏見さんのローカルChromeからYouTube向けCookieを抽出し、Cloudflare KVへpushする。

launchdから1日1回自動実行される想定（README.md参照）。
サーバー側での自動ログインより、本人PCの通常利用に見えるログイン状態を使う方が
Bot判定を受けにくいという設計判断のもとでこの方式を採用している。
"""
import http.cookiejar
import os
import sys
import tempfile

import requests
from yt_dlp.cookies import extract_cookies_from_browser

KV_KEY = 'shared_cookie'
# YouTube本体だけでなく、Googleアカウント関連のCookieもBot判定回避に必要
COOKIE_DOMAINS = ('youtube.com', 'google.com')
# APIトークンはplist（他ユーザーからも読める権限になりがち）に平文で置かず、
# パーミッション600のこのファイルから読む
CF_API_TOKEN_PATH = os.path.expanduser('~/.flare_downloader_cf_token')
# Slack Webhook URLも同様にパーミッション600のファイルから読む
SLACK_WEBHOOK_PATH = os.path.expanduser('~/.flare_downloader_slack_webhook')


def _notify_slack_failure(reason):
    """失敗時にSlackへ通知する。通知自体の失敗は元のエラーを握りつぶさないよう静かにログするだけに留める"""
    try:
        if not os.path.isfile(SLACK_WEBHOOK_PATH):
            print(f'[sync_cookie] {SLACK_WEBHOOK_PATH} が見つからないためSlack通知をスキップします')
            return
        with open(SLACK_WEBHOOK_PATH, 'r', encoding='utf-8') as f:
            webhook_url = f.read().strip()
        text = f'Flare Downloader Cookie同期に失敗しました\n{reason}'
        requests.post(webhook_url, json={'text': text}, timeout=10)
    except Exception as e:
        print(f'[sync_cookie] Slack通知の送信に失敗しました: {e}')


def _read_api_token():
    if not os.path.isfile(CF_API_TOKEN_PATH):
        print(f'[sync_cookie] {CF_API_TOKEN_PATH} が見つかりません。トークンを保存してください')
        sys.exit(1)
    with open(CF_API_TOKEN_PATH, 'r', encoding='utf-8') as f:
        return f.read().strip()


def _extract_netscape_cookies():
    """ChromeのCookieJarから対象ドメインのCookieのみ抜き出し、Netscape形式のテキストに変換する"""
    jar = extract_cookies_from_browser('chrome')

    mozilla_jar = http.cookiejar.MozillaCookieJar()
    for cookie in jar:
        if any(domain in cookie.domain for domain in COOKIE_DOMAINS):
            mozilla_jar.set_cookie(cookie)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
        tmp_path = tmp.name
    try:
        mozilla_jar.save(tmp_path, ignore_discard=True, ignore_expires=True)
        with open(tmp_path, 'r', encoding='utf-8') as f:
            return f.read()
    finally:
        os.remove(tmp_path)


def _push_to_kv(content):
    account_id = os.environ['CF_ACCOUNT_ID']
    namespace_id = os.environ['CF_KV_NAMESPACE_ID']
    api_token = _read_api_token()

    url = (
        f'https://api.cloudflare.com/client/v4/accounts/{account_id}'
        f'/storage/kv/namespaces/{namespace_id}/values/{KV_KEY}'
    )
    res = requests.put(
        url,
        headers={'Authorization': f'Bearer {api_token}'},
        data=content.encode('utf-8'),
        timeout=30,
    )
    res.raise_for_status()
    return res.json()


def main():
    required_env = ('CF_ACCOUNT_ID', 'CF_KV_NAMESPACE_ID')
    missing = [name for name in required_env if not os.environ.get(name)]
    if missing:
        reason = f'環境変数が未設定です: {", ".join(missing)}'
        print(f'[sync_cookie] {reason}')
        _notify_slack_failure(reason)
        sys.exit(1)

    try:
        content = _extract_netscape_cookies()
    except Exception as e:
        reason = f'Cookie抽出に失敗しました: {e}'
        print(f'[sync_cookie] {reason}')
        _notify_slack_failure(reason)
        sys.exit(1)

    if not content.strip():
        reason = 'Cookieが取得できませんでした（Chromeで一度YouTubeにログインしてください）'
        print(f'[sync_cookie] {reason}')
        _notify_slack_failure(reason)
        sys.exit(1)

    try:
        result = _push_to_kv(content)
    except Exception as e:
        reason = f'KVへの書き込みに失敗しました: {e}'
        print(f'[sync_cookie] {reason}')
        _notify_slack_failure(reason)
        sys.exit(1)

    if result.get('success'):
        print('[sync_cookie] Cookieの同期に成功しました')
    else:
        reason = f'KV APIがエラーを返しました: {result}'
        print(f'[sync_cookie] {reason}')
        _notify_slack_failure(reason)
        sys.exit(1)


if __name__ == '__main__':
    main()
