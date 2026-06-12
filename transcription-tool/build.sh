#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== Flare Transcript ビルド ==="

# venv
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate

pip install -q pyinstaller faster-whisper yt-dlp flask

# ビルド
venv/bin/pyinstaller \
  --name "Flare Transcript" \
  --windowed \
  --onedir \
  --add-data "templates:templates" \
  --collect-all faster_whisper \
  --collect-all ctranslate2 \
  --hidden-import faster_whisper \
  --hidden-import ctranslate2 \
  --hidden-import yt_dlp \
  launcher.py

# zip化
cd dist
zip -r "../FlareTranscript-arm64.zip" "Flare Transcript.app"
echo ""
echo "✅ ビルド完了: FlareTranscript-arm64.zip"
