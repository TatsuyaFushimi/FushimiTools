#!/bin/bash
# YouTube Cookie更新スクリプト
# ダブルクリックで実行できます

cd "$(dirname "$0")"

echo "======================================"
echo "  Flare Downloader Cookie更新ツール"
echo "======================================"
echo ""

# yt-dlp の場所を確認
if [ -f "venv/bin/yt-dlp" ]; then
  YTDLP="venv/bin/yt-dlp"
elif command -v yt-dlp &>/dev/null; then
  YTDLP="yt-dlp"
else
  echo "❌ yt-dlp が見つかりません"
  echo "   先に ./start.sh を一度実行してセットアップしてください"
  read -p "Enterを押して終了..."
  exit 1
fi

COOKIES_FILE="/tmp/yt_cookies_$$.txt"

echo "🔍 ブラウザからYouTubeのCookieを取得中..."
echo "   (Chromeのキーチェーンアクセスを求められたら「許可」してください)"
echo ""

# Chrome → Safari の順で試す
if $YTDLP --cookies-from-browser chrome \
          --cookies "$COOKIES_FILE" \
          --skip-download --quiet \
          "https://www.youtube.com/" 2>/dev/null; then
  echo "✅ Chromeからクッキーを取得しました"

elif $YTDLP --cookies-from-browser safari \
            --cookies "$COOKIES_FILE" \
            --skip-download --quiet \
            "https://www.youtube.com/" 2>/dev/null; then
  echo "✅ Safariからクッキーを取得しました"

else
  echo "❌ クッキーの取得に失敗しました"
  echo "   ChromeまたはSafariでYouTubeを開いてからもう一度試してください"
  rm -f "$COOKIES_FILE"
  read -p "Enterを押して終了..."
  exit 1
fi

echo ""
echo "📤 サーバーにアップロード中..."
echo "   (初回アクセスは30秒ほどかかる場合があります)"

RESPONSE=$(curl -s --max-time 90 -X POST \
  https://fushimitools-youtube.onrender.com/api/cookies \
  -F "file=@$COOKIES_FILE")

if echo "$RESPONSE" | grep -q '"ok"'; then
  echo "✅ アップロード成功！"
else
  echo "❌ アップロードに失敗しました: $RESPONSE"
  rm -f "$COOKIES_FILE"
  read -p "Enterを押して終了..."
  exit 1
fi

# Render環境変数にも保存（再起動・再デプロイ後も有効にする）
RENDER_API_KEY=$(grep "key:" ~/.render/cli.yaml 2>/dev/null | head -1 | awk '{print $2}')
if [ -n "$RENDER_API_KEY" ]; then
  echo ""
  echo "💾 環境変数に保存中（デプロイ後も自動で読み込まれます）..."
  COOKIES_B64=$(base64 < "$COOKIES_FILE" | tr -d '\n')
  curl -s --max-time 30 -X PUT \
    "https://api.render.com/v1/services/srv-d8l3bt9o3t8c73ajjgig/env-vars" \
    -H "Authorization: Bearer $RENDER_API_KEY" \
    -H "Content-Type: application/json" \
    -d "[{\"key\":\"YOUTUBE_COOKIES_B64\",\"value\":\"$COOKIES_B64\"}]" > /dev/null
  echo "✅ 環境変数に保存しました"
fi

rm -f "$COOKIES_FILE"

echo ""
echo "======================================"
echo "  完了！"
echo "  https://fushimitools-youtube.onrender.com"
echo "======================================"
echo ""
read -p "Enterを押して終了..."
