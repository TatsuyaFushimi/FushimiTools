# ツール・アプリ一覧

> このプロジェクトで開発したツール・アプリの一覧です。

## 開発済み

### YouTube Downloader
- **概要**: YouTube URLを入力してMP4でダウンロードできるローカルWebアプリ
- **AI必要**: なし
- **フォルダ**: [./youtube-downloader/](./youtube-downloader/)
- **フロー**: URL貼り付け → 情報取得 → 解像度選択 → DLボタン → MP4保存
- **起動方法**: `cd youtube-downloader && ./start.sh` → http://localhost:5000
- **共有方法**: ローカル実行（git clone + venv セットアップ）

## 開発予定・検討中

*要望があれば追記します*

---

## ツール記載フォーマット

```
### ツール名
- **概要**: 何をするツールか
- **AI必要**: あり / なし
- **フォルダ**: ./tool-name/
- **フロー**: 入力 → 処理 → 出力
- **共有方法**: Web / ファイル配布 / etc
```
