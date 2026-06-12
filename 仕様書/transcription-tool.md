# Flare Transcript — サービス構成・動作概要

## 何をするツールか

YouTube URLまたはMP4ファイルの音声を文字起こしするmacOS専用アプリ。
完全ローカル動作のため、外部サービスへのデータ送信なし。

---

## 利用サービス・ライブラリ一覧

| サービス／ライブラリ | 役割 | 備考 |
|-------------------|------|------|
| **faster-whisper** | 音声→テキスト変換（AIモデル） | OpenAI Whisperの高速版。CPU/int8で動作 |
| **yt-dlp** | YouTube URLから音声を抽出 | mp3形式で一時保存 |
| **ffmpeg** | 動画から音声を抽出・変換 | Homebrewでインストール |
| **Flask** | ローカルWebサーバー | localhost:5002で起動。ブラウザがUIになる |
| **PyInstaller** | Python＋依存物をmacOS .appにバンドル | arm64(Apple Silicon)専用ビルド |

外部クラウドサービスは一切使用しない。

---

## 動作フロー

### YouTube URL の場合
```
URLを入力 → 文字起こし開始
  → yt-dlpでYouTubeから音声(mp3)をダウンロード
  → faster-whisperで音声→テキスト変換
  → TXT / SRT形式でダウンロード
```

### MP4ファイルの場合
```
MP4をアップロード → 文字起こし開始
  → ffmpegで動画から音声(mp3)を抽出
  → faster-whisperで音声→テキスト変換
  → TXT / SRT形式でダウンロード
```

---

## Whisperモデルについて

| モデル | サイズ | 速度 | 精度 |
|-------|--------|------|------|
| tiny | 39MB | 最速 | 低 |
| small | 244MB | 標準 | 良好 |
| medium | 769MB | 低速 | 高 |

- モデルは初回使用時に `~/.flare-transcript/models/` へ自動ダウンロード
- 2回目以降はキャッシュを使用（DL不要）

---

## 出力フォーマット

| 形式 | 内容 |
|------|------|
| `.txt` | 本文テキストのみ（改行区切り） |
| `.srt` | タイムスタンプ付き字幕形式（動画編集ソフトに取り込み可） |

---

## ファイル構成

| ファイル | 内容 |
|---------|------|
| `app.py` | Flaskアプリ本体。音声抽出・文字起こしAPI |
| `launcher.py` | .app起動エントリーポイント |
| `templates/index.html` | Web UI |
| `requirements.txt` | Python依存パッケージ |
| `build.sh` | PyInstallerビルドスクリプト |
