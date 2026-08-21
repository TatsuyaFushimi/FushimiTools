# Frame.io連携（開発用） — サービス構成・動作概要

## 何をするツールか

同僚作成の本番Frame.ioアップロードツール（`/Users/fushimi/Documents/Frame.io最新/uploader_tool/`、Node.js + Express）の、
**伏見さん専用の開発・検証用コピー**。ブラウザから動画をFrame.io v4 APIへ直接アップロードし、完了後にSlack通知する機能を持つ。
本番環境には一切影響しない独立フォルダとして運用する。

- **フォルダ**: `Frame.io連携（開発用）/`（本番は `/Users/fushimi/Documents/Frame.io最新/uploader_tool/`、Git管理外・別マシン上の同僚の作業ディレクトリ）
- **AI必要**: なし（現時点。将来のFlarePocket連携時にClaude/Gemini APIが絡む予定 → 「今後の拡張予定」参照）

---

## 本番ツールとの関係

| 観点 | 本番（`uploader_tool/`） | この開発用コピー |
|------|------------------------|----------------|
| `destinations.js` | 編集者マッピング50件超（マネージャー/チャンネル/編集者） | 伏見さんのテスト用1件のみ（`'伏見さん/テスト/伏見さん'`） |
| チャンネル別Slackアラート設定（`frameio_slack_alert_*.yaml`） | あり（複数チャンネル分） | 未コピー（スコープ外） |
| `.env` / `env.txt`（本番認証情報） | あり | 未コピー。`.env.example` を元に伏見さん用の値を別途設定 |
| スプレッドシート連携（`PRODUCTION_MANAGEMENT_SHEET_ID`等） | あり（本番用シート） | 別シート（`PROGRESS_SHEET_ID`＝進捗一覧シート）として独自に実装済み（下記セクション参照） |
| server.js本体のロジック | ベース | 本番からコピーしたものをそのまま使用（現時点で改修なし） |

**今後の想定フロー**: このフォルダで新機能（FlarePocket連携等）を実装・検証 → 検証完了後、本番の編集者マッピング・スプレッドシート連携データを維持したフルコピーに機能をマージ → 元の同僚に渡して本番へ差し替えてもらう。

---

## 利用サービス一覧

| サービス | 役割 | 備考 |
|---------|------|------|
| **Frame.io v4 API** | 動画アップロード先（`local_upload`エンドポイント） | 認証はAdobe OAuth（`FRAME_IO_API_MODE=v4`） |
| **Adobe Developer Console（OAuth）** | Frame.io v4 APIアクセス用トークン発行 | `ADOBE_CLIENT_ID` / `ADOBE_CLIENT_SECRET` |
| **Slack（Bot Token）** | アップロード完了通知 | 開発検証用ワークスペース/チャンネル推奨 |
| **Express（Node.js）** | サーバー本体 | ローカル起動（`http://localhost:3000`） |
| **Google Sheets（進捗一覧シート）** | Slackイベント検知→進捗行の自動作成・更新 | `PROGRESS_SHEET_ID`。実装済み（下記セクション参照） |
| **Slack Events API** | 初稿連絡Bot通知・編集Dスタンプ投稿の検知 | `POST /slack/events`。`TEST_ONLY_CHANNEL_ID`で伏見さん個人チャンネルに限定 |

---

## 動作フロー

```
ブラウザで http://localhost:3000 を開く
  → 保存先（マネージャー/チャンネル/編集者）を選択 ※開発用は伏見さんのテスト用1件のみ
  → 動画ファイルを選択・アップロード
  → server.js が Frame.io v4 API（local_upload）へ直接アップロード
  → 完了後、Slack Bot Tokenでチャンネルへ完了通知を投稿
```

テスト用の保存先を手動選択したい場合は `http://localhost:3000/?test=1` を開く。

---

## 主要ファイル

| ファイル | 内容 |
|---------|------|
| `Frame.io連携（開発用）/server.js` | サーバー本体。Frame.ioアップロード・Adobe OAuth・Slack通知・4点セットのインタラクティブ処理 |
| `Frame.io連携（開発用）/destinations.js` | 保存先マッピング（`マネージャー名/チャンネル名/編集者名`の3階層キー）。`slackId`は`editorDSlackId`（編集D）と`planDSlackId`（企画D）の2フィールドに分割済み |
| `Frame.io連携（開発用）/action-messages.local.json` | 4点セットの状態（企画D確認・編集D確認の完了フラグ、修正期日・確認期日）をファイルベースで保存するストア |
| `Frame.io連携（開発用）/.env.example` | 環境変数テンプレート（本番のスプレッドシート連携項目は除外済み） |
| `Frame.io連携（開発用）/README.md` | 起動方法・本番との差分・本番反映方法 |

---

## Slackインタラクティブ機能「4点セット」（実装済み・ライブテスト完了 2026-08-20）

アップロード完了通知のSlackメッセージに、以下4つの操作要素を追加する機能。実装・実チャンネルでのライブテストが完了し、ユーザー最終確認OK済み。

- **企画D確認ボタン**（赤 `style: danger`）
- **編集D確認ボタン**（緑 `style: primary`）
- **修正期日 datepicker**（企画D確認・編集D確認の両方が完了するまでロック＝ボタン自体を非表示）
- **確認期日 datepicker**

ブロック表示順：確認期日 → 企画D/編集D確認ボタン → 修正期日。

### 処理フロー
1. `postActionSet(threadKey, destinationKey)`（`server.js`）がアップロード完了通知に4点セットのBlock Kitを付与して投稿（`POST /api/test-post-action-set`で単体テスト可）
2. ユーザーがボタン押下・日付選択 → `POST /slack/interactions` が受信
   - 署名検証（HMAC SHA256、5分タイムスタンプ制限、fail-closed）
   - 権限チェック（`destinations.js`の`planDSlackId`/`editorDSlackId`とpayload.user.idの一致確認。他人の確認ボタンは押せない）
   - 修正期日はサーバー側でも「企画D確認・編集D確認の両方完了済みか」を二重チェック
   - 状態更新 → `action-messages.local.json`に保存
3. `updateActionSetMessage(channel, ts, state)` が `chat.update`（`SLACK_BOT_TOKEN`使用）でメッセージを書き換え

### 設計上のポイント（実運用でしか見えなかった制約）
- **Slack Block Kitの`disabled`プロパティはbutton/datepickerで使用不可**（付与すると`invalid_blocks`エラー）。`buildActionSetBlocks(state)`は非活性化ではなく、状態に応じてinteractiveなactionsブロックと静的なsectionテキストブロックを丸ごと出し分ける方式で対応
- **`response_url`は30分/5回までの使用制限がある**ため、ボタン操作後の非同期UI更新には使わず、`chat.update`（Bot Token使用）を採用

詳細な教訓は `knowhow.md`「Slack Block Kitインタラクティブ機能の実装ハマりポイント」を参照。

---

## 進捗一覧シート連携機能（実装済み・2026-08-21）

Slackのメッセージイベントを検知し、Google Sheets「進捗一覧シート」への行の自動作成・更新を行う機能。

- **`POST /slack/events`**：Slack Events APIの受信口。署名検証、`url_verification`応答、`message`イベント検知を行う
- **`TEST_ONLY_CHANNEL_ID`によるチャンネル限定ガード**：このチャンネルID以外で発生したイベントは処理の先頭で即無視する（`server.js` 2370行目付近）。安全のため必須設定
- **検知1：初稿連絡Bot通知** → 進捗一覧シートへ新規行を作成（状況＝「編集D確認中」）
- **検知2：編集Dの初稿スタンプ投稿**（`FIRST_DRAFT_STAMP_EMOJI`で判定） → 該当行を更新（状況＝「初稿確認」）＋4点セットを接続
- **4点セットのボタン操作結果**を進捗一覧シートへピンポイント反映
- **`POST /api/admin/setup-progress-tabs`**：制作管理シートのチャンネルタブとSlack参加チャンネルを突き合わせ、進捗一覧シートに不足しているタブを自動作成する管理用エンドポイント
- **環境変数**：`PROGRESS_SHEET_ID`（進捗一覧シートのID）、`FIRST_DRAFT_STAMP_EMOJI`／`REVISION_STAMP_EMOJI`／`LIMITED_RELEASE_STAMP_EMOJI`（3種のスタンプ絵文字ショートコード。Slackへの絵文字登録済み：`初稿受領_編集ディレクター`／`修正稿_編集ディレクター`／`限定公開_編集ディレクター`）、`TEST_ONLY_CHANNEL_ID`
- **タイトル抽出は「」のみ**（【】は廃止。タイトル自体に【】が含まれるケースがあるため誤抽出を避けた）
- 修正稿・限定公開スタンプの検知処理（状況更新等）は**今回スコープ外・未実装**（環境変数は将来実装用に用意済み）

### 実機テストで発生した無限ループ事故と対処（重要）

実機テスト中、Slack「fushimi個人用」チャンネルに**124件のスパムメッセージ**が投稿される無限ループ事故が発生した（全件削除済み。実害はメッセージスパムのみで、シートへの誤書き込みは確認されていない）。

**原因**：初稿連絡Bot通知の検知条件が「投稿元Botの`bot_id`が一致するか」のみだったため、`server.js`自身がSLACK_BOT_TOKENで投稿するあらゆるメッセージ（エラーアラート等）まで同じBot IDとして誤検知され、「アラート投稿→誤検知→解析失敗→新たなアラート投稿→誤検知…」のループに陥った。

**対処**：①自己投稿を示す目印（`INTERNAL_SLACK_POST_MARKER`、ゼロ幅文字）を全投稿の文末に付与し検知処理の先頭で除外、②検知条件を「`bot_id`一致 AND 初稿連絡Bot通知テンプレート特有の固定文言を含む」の二重条件に強化＋重複行防止チェックを追加、③テスト2回目・レビュー時に発覚した付与漏れ箇所（`/api/notify`のメイン・フォールバック投稿、4点セット更新の`chat.update`）を修正し、Bot自身が投稿する全経路（`chat.postMessage`5箇所＋`chat.update`1箇所）に統一。

詳細な原因分析・教訓は `knowhow.md`「Slackメッセージ検知の無限ループ事故」を参照。

---

## 起動方法（開発用）

```bash
cd "Frame.io連携（開発用）"
npm install
cp .env.example .env
# .envを開いて各項目に実際の値を入れる（Frame.ioトークン・Adobe OAuth・Slack Bot Token等）
npm start
```

起動後、ブラウザで `http://localhost:3000` を開く。

---

## 今後の拡張予定

このフォルダをベースに、伏見さんが運用する別ツール「FlarePocket」（`/Users/fushimi/Documents/ClaudeCode/FlarePocket_PJ/`、
動画自動添削。Frame.io Webhook起点で添削→コメント投稿まで実装済み）の機能を段階的に組み込んでいく。

1. アップロード＋Slack通知（実装済み）
2. Slackインタラクティブ「4点セット」（企画D/編集D確認ボタン・修正期日/確認期日datepicker、実装済み・ライブテスト完了2026-08-20。詳細は上記セクション参照）
3. 進捗一覧シート連携（実装済み・2026-08-21。詳細は上記セクション参照）
4. FlarePocket自動添削機能の組み込み（Claude/Gemini APIを使った動画添削処理。将来的にAI利用が発生する箇所）
5. Slackスレッド返信機能
6. Frame.ioコメント投稿機能
7. 上記が固まった段階で、本番データを維持したフルコピーへマージし、同僚経由で本番差し替え

導入は最後のフェーズ（順番はユーザー確認のうえ変わる可能性あり）。

---

## 現状のスコープ外事項

- 本番のスプレッドシート連携（`PRODUCTION_MANAGEMENT_SHEET_ID`）そのもの（開発用は別シート`PROGRESS_SHEET_ID`で独自実装済み。上記セクション参照）
- 修正稿・限定公開スタンプの検知処理（状況更新等）→ 環境変数は用意済みだが処理は未実装
- チャンネル別Slackアラート設定（`frameio_slack_alert_*.yaml`）
- 本番の編集者マッピング（50件超）→ 伏見さんのテスト用1件のみに簡略化
- FlarePocketとの連携（AI添削・Slackスレッド返信・Frame.ioコメント投稿）は未実装、今後の拡張予定
