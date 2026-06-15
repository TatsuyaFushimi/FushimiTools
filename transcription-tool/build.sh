#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== Flare Scribe ビルド ==="

# venv
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate

pip install -q pyinstaller faster-whisper yt-dlp flask

# ビルド
venv/bin/pyinstaller \
  --name "Flare Scribe" \
  --windowed \
  --onedir \
  --icon "static/icon.png" \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --collect-all faster_whisper \
  --collect-all ctranslate2 \
  --hidden-import faster_whisper \
  --hidden-import ctranslate2 \
  --hidden-import yt_dlp \
  launcher.py

# LSUIElement追加（バックグラウンドアプリ化→Dockで跳ね続けない）
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "dist/Flare Scribe.app/Contents/Info.plist" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :LSUIElement true" "dist/Flare Scribe.app/Contents/Info.plist"

# zip化
cd dist
zip -r "../FlareScribe-arm64.zip" "Flare Scribe.app"
echo ""
echo "✅ ビルド完了: FlareScribe-arm64.zip"
