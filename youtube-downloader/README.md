# Flare Downloader

YouTube動画をMP4でダウンロードできるローカルWebアプリ。

## 初回セットアップ

```bash
# ffmpeg がない場合（高画質DLに必要）
brew install ffmpeg

# 依存パッケージをインストール
cd youtube-downloader
python3 -m venv venv
venv/bin/pip install flask yt-dlp
```

## 起動方法

```bash
./start.sh
```

ブラウザで http://localhost:5000 を開く（自動で開かない場合）。

## 使い方

1. YouTube URLを貼り付け →「情報取得」
2. 解像度を選択（デフォルトは最高画質）
3.「ダウンロード」→ MP4ファイルが保存される

## 停止方法

ターミナルで `Ctrl + C`
