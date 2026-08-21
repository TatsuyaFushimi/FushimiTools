# 開発ノウハウ

このプロジェクトで蓄積した知見・パターン・提案アイデアをまとめるファイル。

---

## 実装パターン

### AI不要（プログラムのみ）で実現できるもの
- テキスト変換・整形（文字カウント、フォーマット変換）
- 計算ツール（各種計算機、単位変換）
- データ可視化（CSV読み込み→グラフ）
- フォーム→PDF生成
- QRコード生成
- 画像リサイズ・圧縮（ブラウザ上）
- JSONフォーマッター・バリデーター
- 正規表現テスター
- タイマー・ストップウォッチ・カウントダウン
- マークダウンエディタ

### Claude AI があると価値が上がるもの
- 文章生成・要約・添削
- 自然言語でのデータ分析・解釈
- 画像内テキスト認識・解析
- カスタマーサポートチャット
- 複雑な分類・タグ付け自動化
- 多言語翻訳（高精度）

---

## 共有方法の選択基準

| 方法 | 向いているケース |
|------|----------------|
| HTMLファイル単体 | バックエンド不要・オフライン使用・手軽に配布 |
| GitHub Pages | 静的サイト・無料・URLで共有 |
| Vercel | React/Next.js・API Routes必要な場合 |
| ローカルサーバー | 社内のみ・セキュリティ重視・大容量データ |

---

## 提案できる機能アイデア（要望次第で展開可能）

- 議事録自動生成（音声→テキスト→要約）
- 社内FAQ検索ツール（PDF読み込み→質問応答）
- スケジュール調整補助ツール
- 見積もり自動計算フォーム
- 名刺データ取り込み→CSV出力
- ランディングページジェネレーター
- アンケート集計・可視化ダッシュボード

---

## Premiere Pro CEP エクステンション開発（Flare Drive Browser）

### 基本構成
- **方式**: CEP（CSXS 11.0）。HTML/CSS/JS パネル + ExtendScript ブリッジ
- **インストール**: `sudo cp -r ./premiere-extension/. "/Library/Application Support/Adobe/CEP/extensions/com.busoken.drive-asset-browser/"`
- **デバッグモード有効化**: `defaults write com.adobe.CSXS.11 PlayerDebugMode 1`
- **ファイル構成**: `index.html` / `main.js` / `styles.css` + `CSXS/manifest.xml` + `jsx/host.jsx`

### Node.js アクセス（重要）
- **`--mixed-context` フラグ**: Premiere Pro 26.x（2024）では**機能しない**。`require` が undefined になる
- **NodeMain**: Premiere Pro 26.x では**機能しない**。プロセスが起動しない
- **結論**: PPro 26.x ではパネル JS 側から Node.js にアクセスする方法が現状ない
- **代替案**: 別途ヘルパー Mac アプリ経由でファイル操作する設計にする

### バイナリファイルDL（Node.js なし時）
- `fetch()` → `arrayBuffer()` → base64 文字列 → `window.cep.fs.writeFile`（UTF-8）→ ExtendScript `decodeAndSave()` でバイナリ変換
- `window.cep.fs.writeFile` はバイナリ不可（UTF-8のみ）。エラーコード 5 が返る
- 速度: 3MB ファイルで数十秒（ExtendScript デコードがボトルネック）

### CEP で使える API
- `window.cep.fs` — ファイル読み書き（writeFile は UTF-8 のみ）
- `window.cep.dnd.initiateDrag(mouseEvent, [filePath], [''])` — ファイルをタイムラインへドラッグ
- `window.__adobe_cep__.evalScript(script, callback)` — ExtendScript 呼び出し
- `fetch()` — HTTP リクエスト（CORS 制限あり、Drive API は OK）

### ExtendScript（host.jsx）でできること
- `new File(path)` で binary モード書き込み可能（`encoding = 'BINARY'`）
- `File.copy(destPath)` — ファイルコピー（mogrt → テンプレートフォルダ）
- `app.project.importFiles([path], ...)` — Premiere プロジェクトへ取り込み
- `Folder.home.fsName` — ホームディレクトリパス

### ドラッグ＆ドロップの実装
- `mousedown` → 5px 移動で drag 開始判定 → ファイルDL → `cep.dnd.initiateDrag`
- mogrt はクリックで「テンプレートに追加」、他ファイルはドラッグのみ
- DL 済みのローカルファイルがあれば即ドラッグ（待ち時間なし）

---

## Premiere Pro UXP プラグイン開発（Flare Drive Browser v2）

### CEP → UXP 移行の理由
- PPro 26.x では `--mixed-context` / NodeMain が動かず Node.js にアクセス不可
- UXP は `require('fs')`, `require('path')`, `require('os')` がネイティブに使える
- `localFileSystem: "fullAccess"` 権限を manifest.json で宣言するだけで有効

### manifest.json 構成
```json
{
  "manifestVersion": 5,
  "id": "com.busoken.flareDriveBrowser",
  "host": [{ "app": "PPRO", "minVersion": "22.0" }],
  "entrypoints": [{ "type": "panel", "id": "panel1", "main": "index.html" }],
  "requiredPermissions": {
    "localFileSystem": "fullAccess",
    "network": { "domains": ["https://www.googleapis.com", ...] }
  }
}
```

### UXP でのバイナリダウンロード
- `fetch()` + `arrayBuffer()` + `new Uint8Array(buffer)` + `fs.writeFileSync()` で完結
- `require('https')` 不要・リダイレクトも fetch が自動処理

### Premiere Pro への取り込み（UXP API）
```javascript
const ppro = require('premierepro');
const project = await ppro.Project.getActiveProject(); // または ppro.getActiveProject()
await project.importFiles([filePath], true, project.rootItem, false);
```
- API 形式はバージョンにより差異あり。複数形式を try/catch で試す設計が堅牢。

### mogrt インストール（UXP, ExtendScript 不要）
```javascript
fs.copyFileSync(srcPath, path.join(os.homedir(), 'Documents', 'Motion Graphics Templates', basename));
```

### ドラッグ（UXP / HTML5 アプローチ）
- `draggable="true"` + `dragstart` で `text/uri-list: file://...` をセット
- Premiere タイムラインへ直接ドロップできるか要テスト（CEP の `cep.dnd.initiateDrag` 相当は UXP に存在しない）
- 動作しない場合はクリック→プロジェクト Bin 追加が確実な代替手段

### インストール方法（開発中）
1. Creative Cloud で "Adobe UXP Developer Tools" をインストール
2. UXP Developer Tools を起動 → "Add Plugin" → manifest.json のあるフォルダを選択
3. Premiere Pro を起動 → UXP Developer Tools でプラグインを "Load" or "Load and Watch"
4. PPro のウィンドウメニューから "Flare Drive Browser" を開く

### フォルダ構成（CEP との違い）
| 項目 | CEP | UXP |
|------|-----|-----|
| 設定ファイル | CSXS/manifest.xml | manifest.json |
| JSブリッジ | jsx/host.jsx + evalScript | 不要（premierepro API） |
| Node.js | 不可（PPro 26.x） | 常時利用可能 |
| インストール先 | CEP/extensions/ | UXP Developer Tools |

---

## 要望パターンと対応メモ

*ツールを作るたびに追記していく*

---

## GAS（Google Apps Script）へのPOSTリクエスト

### 問題
`fetch` で GAS の doPost エンドポイントに `Content-Type: application/json` ヘッダーを付けると、ブラウザが CORS プリフライト（OPTIONS リクエスト）を送信する。GAS は OPTIONS を処理できないため、実際の POST が届かない。

### 解決策
GAS へ POST するときは `Content-Type` ヘッダーを**付けない**。
ヘッダーなしの場合、fetch のデフォルトは `text/plain;charset=UTF-8` になり、シンプルリクエスト扱いでプリフライトが発生しない。
GAS 側は `e.postData.contents` で body 文字列を受け取れるため、`JSON.stringify` した body を `JSON.parse(e.postData.contents)` でパースできる。

### コード例
```typescript
// ✅ 正しい（Content-Typeヘッダーなし）
fetch(GAS_URL, {
  method: 'POST',
  body: JSON.stringify({ key: 'value' }),
}).catch(() => {});

// ❌ 誤り（CORSプリフライトが発生してGASに届かない）
fetch(GAS_URL, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ key: 'value' }),
}).catch(() => {});
```

### 適用箇所
- YouQR `admin.ts`：管理画面ロード時のトークン自動保存（2026-07-21修正済み）

---

## テンプレートリテラル内 `<script>` への TypeScript 型注釈混入

Cloudflare Workers の admin.ts は HTML をテンプレートリテラルとして定義し、Worker が文字列として返す設計。
テンプレートリテラル内の `<script>` ブロックは TypeScript コンパイラがトランスパイルしないため、
`: string` 等の型注釈がそのままブラウザに届き `SyntaxError` になる。
→ `let qrLogoMode: string =` ではなく `let qrLogoMode =` のように型注釈なしで書く。

---

## BoxURL_PJ を別CHに流用する手順

GAS（trigger.gs）を別CH用に複製するときの変更箇所と注意点。

### 変更箇所（7点）

| ファイル | 場所 | 変更内容 |
|---|---|---|
| trigger.gs | CONFIG `SPREADSHEET_ID` | 新CHのスプレッドシートIDに変更 |
| trigger.gs | CONFIG `SHEET_NAME` | 新CHのシート名に変更 |
| trigger.gs | CONFIG `BOX_PARENT_FOLDER_ID` | 新CHのBoxフォルダIDに変更 |
| trigger.gs | CONFIG `BOX_FILE_REQUEST_TEMPLATE_ID` | 新CH用に別途File Requestテンプレートを作成した場合はそのIDに変更（同じテンプレートを使い回す場合は変更不要） |
| trigger.gs | CONFIG `SLACK_WEBHOOK_URL` | 新CH用Webhookに変更（別チャンネル通知なら新規発行が必要） |
| trigger.gs | CONFIG `SLACK_MENTION_USER_IDS` | 新CHの担当者SlackユーザーIDに変更 |
| trigger.gs | `_buildFolderName` | フォルダ名プレフィックスを変更（例：`【自社動画】`を削除して`${today}_${title}`のみにする等） |
| trigger.gs | `_postReadyToSlack` の `const text` | 投稿文をCH名に合わせて変更（`${mentions}` を含めること） |

### 注意事項

- **必ず別GASプロジェクトとして作成する**。同一プロジェクトに複数のtrigger.gsを入れると `const CONFIG` が二重定義されてプロジェクト全体が起動不能になる
- `const text` に `${mentions}` を含め忘れると、担当者へのSlackメンションが届かなくなる
- Slack WebhookはSlackチャンネルに紐づくため、別チャンネルに通知する場合は新規Webhookを発行する
- GASプロジェクト新規作成時はBox OAuth2認証を再実行する（`setupOAuth2Config()` → `getAuthorizationUrl()`）
- 認証後に `setupTrigger()` と `setupWeeklyTrigger()` を実行する

### 松永さんch用ひな形
`/Users/fushimi/Documents/ClaudeCode/BoxURL_PJ/gas/trigger_matsunaga.gs`（TODO箇所4点が残存、明日MTG後に差し込み）

---

## BoxURL_PJ: File Request URL は相対パスで返ってくる

Box API の `POST /file_requests/{template_id}/copy` は、コピー成功時のレスポンス `url` が
`https://app.box.com/f/xxxx` のフルURLではなく `/f/xxxx` の**相対パス**で返ってくる場合がある（実機確認済み）。
→ `src/box_client.py` の `copy_file_request()` で `url.startswith('/')` を判定し、`https://app.box.com` を前置してフルURLに変換している。他のBox API連携でも同様の相対パス返却に注意する。

File Request機能はフォルダ単位で「新規発行」するAPIが存在しないため、Box上に手動で1つだけテンプレートとなるFile Requestを作成し、
それを`/copy`エンドポイントで複製する設計にしている（`BOX_FILE_REQUEST_TEMPLATE_ID`が起点）。テンプレート自体を消すと全チャンネルのFile Request発行が止まるため、削除しない。

---

## プロジェクトフォルダ名変更時、Claude Codeのメモリが引き継がれない

### 問題
Claude Codeのプロジェクトメモリ（`~/.claude/projects/[project-slug]/memory/`）は、プロジェクトのフルパスから自動生成されたスラッグ名のフォルダに保存される。
プロジェクトフォルダをリネームすると（例：「アプリ化PJ」→「Claude作業室」）、フルパスが変わるため**新しいスラッグ名のフォルダが自動生成され、旧フォルダの内容は自動では引き継がれない**。
旧メモリフォルダは削除されずに残るが、Claude Codeからは新しいパスのフォルダしか参照されなくなり、過去の知見・プロジェクト状況（memory配下のファイル、MEMORY.md索引）が失われたように見える。

### 解決策
プロジェクトフォルダをリネームする際は、以下を手動で行う。

1. 旧メモリフォルダを特定する：`~/.claude/projects/` 配下を `ls` し、旧フルパスをスラッグ化したフォルダ名（例：`-Users-xxx-旧フォルダ名`）を探す
2. 新メモリフォルダ（`~/.claude/projects/[新スラッグ]/memory/`）に、旧フォルダの `memory/` 配下の全ファイル（`MEMORY.md` 含む）を手動コピーする
3. コピー後、`MEMORY.md` の索引リンクが新フォルダ内のファイルと一致しているか確認する（ファイル名の食い違い・リンク切れがないか）
4. 旧メモリフォルダは念のため削除せず残しておく（万一のコピー漏れに備える）

### 注意
- フォルダ名変更は「今後リネームする予定がある／した」場合に都度発生しうる問題。プロジェクトフォルダをリネームしたら**必ずこの手順を思い出すこと**
- 恒久対策（シンボリックリンク化等）は別途ユーザー承認のうえで検討する

---

## video-slide-maker フェーズ1実装で得た知見（2026-08-03、2026-08-05更新）

### 【不採用】`-webkit-line-clamp` はflex子要素と組み合わせると効かないことがある（旧方式）

`display: -webkit-box` + `-webkit-line-clamp` による文字数省略（`...`表示）は、対象要素が `flex: 1` 等でflexコンテナの子として高さを決定される場合、正しく効かないケースがある。flexアイテムは高さが可変・伸縮する前提のため、line-clampが期待する「固定行数で高さが決まる」挙動と競合する。
→ 当初の対策として「line-clampを使う要素の親を非flexなレイアウト（`display: grid` 等）にする」方式を採用していたが、**最終的に不採用**。下記の理由によりJS計算方式に置き換えた。

### 【採用】html-to-imageでのPNG書き出しを考慮し、文字省略はJS側でcanvas measureText計算する方式（2026-08-05）

`-webkit-line-clamp`（CSSの省略記号`...`）は、`html-to-image` によるDOM→PNGのラスタライズ処理では反映されないことが判明（ブラウザ画面上は正しく省略表示されるが、書き出したPNGには反映されず全文がはみ出す）。non-flexレイアウトに変更しても、この根本問題（ラスタライズとCSS省略記号の非対応）は解決しない。
→ 最終方式：
1. `.card` 自体は `flex` レイアウトのまま維持し、`min-height: 0` を指定（flex子要素でoverflow計算が正しく効くようにするため必須）
2. 文字の省略表示はCSSに頼らず、JS側で `canvas.measureText()` を使い、表示幅に収まる文字数を実測 → 省略記号付きの文字列を計算 → その文字列を要素の `textContent` として直接描画する
3. これにより画面表示・PNG書き出しの両方で省略結果が完全に一致する
→ CardGridテンプレートの文字省略で採用。同様の省略表示が必要な箇所は今後もこの方式で統一する。

### ホバー等の状態変化を背景色の濃淡だけで作るとコントラスト比不足になりうる

背景色の明度をわずかに変えるだけのホバー・選択状態は、実測でWCAG目安（3:1）に対しコントラスト比1.09〜1.42程度にしかならないケースがあった（実質ほぼ視認できない）。
→ 対策：色相の異なるアクセントカラーの枠線（`box-shadow: inset 0 0 0 2px <accent>` 等）を併用する。背景の濃淡だけに頼らず、枠線という別の視覚チャネルでコントラストを確保する。

### Vite + React + TS の静的サイトをGitHub Pages配下に置く場合

`vite.config.ts` の `base` を相対パス（`'./'`）にしておくと、リポジトリ内のどのサブパスに配置しても（トップレベルでもサブフォルダでも）動く。配置場所が未確定・変更されうる段階では特に有効。

### サブエージェントへの実装依頼時、同一フォルダの排他性に注意

同一フォルダで複数のエージェントが並行して作業すると、`npm create vite --overwrite` のような破壊的コマンドとの組み合わせでファイルの衝突・消失が起きうる。
→ 対策：実装依頼時は対象フォルダが他のエージェントの作業と衝突しないか確認し、作業前に必ず現状をReadさせる指示を徹底する。

### 静的コード確認・ビルド成功だけでは実ブラウザのUI不具合を検知できない

`npm run build` が通ること・コードレビューで問題が見えないことと、実際のブラウザでの見た目（レイアウト崩れ、コントラスト不足、ホバー時の視認性等）が正しいことは別の話。テストゥンの実ブラウザテストで複数バグが発見された実績あり。
→ 対策：UI変更を伴う修正は、ビルド確認だけで終わらせず必ず実ブラウザでの再検証をセットにする。

### テンプレートの固定サイズ要素と可変レイアウト（ワイプ等）の組み合わせで本文表示領域がゼロになりうる（2026-08-05）

CardGridテンプレートで「アイコン（固定px指定）」＋「見出し（高さ制約なし）」＋「ワイプ（デフォルトサイズを700pxに引き上げ）」を組み合わせたところ、6〜8項目のカード／箇条書きテンプレートで本文・見出しが完全に消失する崩壊が発生した。さらにワイプを350pxに戻した後も、「アイコン付き6項目×ワイプ角位置配置」の組み合わせでは同種の消失が別途発生した。

原因は、アイコン・見出しなど「固定サイズまたは無制限に伸びうる要素」が、ワイプ等の可変レイアウトによって利用可能幅・高さが縮んだときに、本文（body）の残り面積を静かにゼロまで圧迫してしまうこと。個々の要素は単体では問題なく見えるため、テンプレート単体のレビューでは気づきにくく、「特定の項目数×特定の配置×特定のサイズ」という組み合わせで初めて顕在化した。

→ 対策（採用した方式）：
1. アイコンを持つコンテナに `container-type: inline-size` を指定し、アイコンサイズをコンテナクエリで可変化する（固定pxをやめ、利用可能幅に応じて縮小できるようにする）
2. 見出しに `max-height` を設定し、見出しが本文領域を無制限に侵食しないようにする
3. 本文（body）には最低1行分の `min-height` を確保し、面積が完全にゼロになる事態そのものを防ぐ

→ 教訓：固定サイズ要素（アイコン・見出し等）を含むテンプレートに、後から可変幅・可変サイズの要素（ワイプ、サイドバー等）を追加する場合は、「項目数が多い」「配置によって利用可能領域が狭まる」極端なケースを想定して本文の最低表示領域を明示的に保証する設計にする。`container-type: inline-size` + コンテナクエリは、こうした固定サイズ要素の可変サイズ化に有効。

---

## video-slide-maker Canva風UI移行で得た知見（2026-08-12）

フロントエンド全般で今後も応用できる教訓4点。

### フローティングツールバー等のバースト処理は、選択対象識別子を`key` propとして渡さないとstale refで別要素に誤反映する

字間・行間・透明度スライダーのような「連続操作をデバウンスしてUndo単位にまとめる」バースト処理を、選択中の要素に対して行うコンポーネント（今回のFloatingToolbar）では、ユーザーが選択対象を切り替えながら連続操作する可能性がある。
コンポーネントをマウントしたまま内部stateやrefだけで選択対象を切り替えると、直前の操作対象を指したstale refが残り、切り替え後の操作が別要素に誤って反映されるバグが起きる。
→ 対策：選択中の要素IDを`key` propとしてコンポーネントに渡し、選択対象が変わったら強制的にアンマウント/リマウントさせる。これによりrefやローカルstateがクリーンな状態から再生成され、stale refによる誤反映を防げる。

### `transform: scale`等の視覚的変形を伴う自動計算ロジックで`getBoundingClientRect()`を使うと自己参照ループに陥る危険がある

ワイプの自動回避ロジックで、要素の現在サイズを`getBoundingClientRect()`で取得して次の配置を計算する実装にしたところ、既に自分自身が適用した`transform`（スケール変形）後のサイズを再度読み取ってしまい、計算→transform適用→再計算→…の自己参照ループに陥り、アプリ全体がクラッシュしてデータが消失する重大バグになった（video-slide-makerで実際に発生）。
→ 対策：`getBoundingClientRect()`のような「現在の描画結果」を読むAPIではなく、position情報（元データの座標・サイズ）を直接参照する。もしくは計測前に一時的に変形を解除してから測る。視覚的変形を伴う要素の自動配置・自動回避ロジックを書くときは、常に「自分が適用した変形後の値を読み返していないか」を疑う。

### CSS Modulesで複数クラスを跨いで適用する場合、`position`等の重要プロパティはクラスの結合順序で意図せず上書きされうる

比較テンプレート（SideBySide）で、共通コンポーネント`ItemPositionBox`にCSS Modulesの複数クラスを結合して適用したところ、クラスの結合順序次第で`position`プロパティが意図せず上書きされ、2項目目以降が画面外に消える深刻なバグが発生した。
→ 対策：汎用コンポーネント（複数の呼び出し元から様々な`className`を渡されうるもの）は、外部から渡されるclassNameの結合順序に左右されないよう、レイアウトの根幹となる重要プロパティ（`position`等）はインラインスタイルで直接指定して保証する。CSSクラスの優先順位に依存させない。

### アプリ全体をReact Error Boundaryで覆っておくと、予期しないクラッシュ時のデータロスリスクを軽減できる

上記の自己参照ループバグ発見時、Error Boundaryがない状態だとクラッシュ＝画面が真っ白になりUndo履歴ごとデータが失われる状況だった。
→ 対策：アプリ全体（またはエディタ画面全体）をReact Error Boundaryで覆っておく。バグそのものの再発防止にはならないが、予期しないクラッシュが発生した際に画面遷移を止め、ユーザーに状況を伝えつつ復旧の余地を残す安全網として機能する。

---

## ローカルTTSモデル導入時のハマりポイント（text-to-speech、2026-08-07）

### Irodori-TTSはPyPI未公開。GitHubリポジトリを直接cloneし`uv sync --extra cpu`で依存解決する

`Aratako/Irodori-TTS-500M-v2` はPyPIパッケージとして配布されていないGitHubリポジトリ（`Aratako/Irodori-TTS`）。
`pip install` では入らないため、リポジトリをclone（特定コミットに`checkout`して固定）し、`uv sync --extra cpu` で依存解決する必要がある。
torch, transformers, dacvae, silentcipher等の重い依存が含まれるため、初回セットアップの`uv sync`にはそれなりの時間がかかる。

### Python API呼び出しは`irodori_tts.inference_runtime`モジュールが正規ルート

CLIの`infer.py`をsubprocessで直接叩く方式は不要。`irodori_tts.inference_runtime` モジュールが提供する
`get_cached_runtime` / `SamplingRequest` / `save_wav` 等を使ってPythonから直接呼び出すのが正規のAPI利用方法。
モデルのロード・キャッシュもこのモジュール側（`get_cached_runtime`）に任せられるため、プロセス内で使い回せば2回目以降の推論が速い。

### vendoredソースはeditable install非対応。`sys.path.insert`で参照する

`irodori_tts_src/` はプロジェクト内に別途`uv sync`済みのvendoredリポジトリであり、site-packagesにはインストールされない構成（editable installに対応していない）。
そのため呼び出し元の`app.py`側で `sys.path.insert(0, IRODORI_SRC_DIR)` を実行してからモジュールをimportする方式が有効だった。

### Gemini TTS無料枠は実際には非常に厳しい（RPD=10程度）

Google AI Studioのご本人アカウントのRate Limitページで実測確認した結果、Gemini TTSの無料枠は1日あたりのリクエスト数（RPD）が10程度と非常に厳しい水準だった。
個人の軽い利用であっても、公式の無料枠だけに頼る設計はすぐに枯渇するリスクがあるという知見。ローカルTTS（Irodori-TTS等）を検討する動機の一つになった。

### macOS標準`say`コマンド＋`ffmpeg`も「完全無料・無制限・低リスク」な代替案として有効

macOS標準搭載の`say`コマンドで音声合成し、`ffmpeg`でMP3化する方式も検討候補になる。
音質はIrodori-TTS等の専用TTSモデルに劣るが、モデルダウンロード・重い依存解決が一切不要で、完全無料・無制限・環境依存のリスクが最も低い。
今回はIrodori-TTSを選定したが、音質を妥協してでも確実性・導入の速さを優先する場面では`say`＋`ffmpeg`方式が有力な代替案になる。

---

## ローカルニューラルTTSモデルは小規模モデルだとひらがなレベルの読み間違いが起きうる（text-to-speech、2026-08-08）

### 実例：Irodori-TTSが「りさちゃん」を「りかちゃん」と誤読

上記でIrodori-TTS（`Aratako/Irodori-TTS-500M-v2`、パラメータ規模500M程度）を採用し実運用してみたところ、
「りさちゃん」と入力すると「りかちゃん」と読み上げるなど、**ひらがなレベルでの読み間違いが頻発**することが判明した。
漢字の読み分け（アクセント辞書がカバーしきれない固有名詞等）でのミスは想定内だが、ひらがな入力でも誤読が起きる＝
テキスト→音素変換の精度自体がパラメータ規模の小さいモデルでは実用レベルに達していない、ということを示す実例。

→ 教訓：ローカルニューラルTTSモデルを採用する際は、パラメータ規模が小さいモデル（数百M程度）ほど、
漢字だけでなくひらがなレベルでも読み間違いが起きうることを前提にテストする。「短いひらがな固有名詞（人名・キャラ名等）を
実際に読ませてみる」検証を、採用判断前に必ず行うべき。

### 精度に不安がある場合、まずmacOS標準`say`＋`ffmpeg`を検討する

上記の読み間違い問題を受け、Irodori-TTSからmacOS標準の`say`コマンド（`Kyoko`/`Otoya`）＋`ffmpeg`によるMP3変換方式に乗り換えた。
結果、実装が大幅にシンプルになり（GitHub clone・`uv sync`等の重い依存解決が不要）、生成速度も約35秒→約0.7秒に高速化し、
読み間違いのリスクも大きく下がった（OS標準の辞書ベース変換のため）。

→ 教訓：「ローカルAIモデルの方が高品質なはず」という先入観で専用ニューラルTTSモデルから検討を始めがちだが、
精度・信頼性に不安がある場合は、まず**OS標準の`say`コマンド＋`ffmpeg`という選択肢を先に検討する**べき。
実装がシンプル・高速・読み間違いリスクが低いというメリットが、音質面の妥協を上回るケースは多い。

### `say`コマンドをPythonから安全に呼ぶ際のTips

- `subprocess.run([...], shell=False)` で配列渡しにする（shell経由のコマンドインジェクションを防ぐ）のは基本
- **さらに、引数リストに `--`（オプション終端）を挟む**とよい。例：
  ```python
  subprocess.run(['say', '-v', VOICE, '-o', aiff_path, '--', text], shell=False)
  ```
  ユーザー入力の`text`が万一 `-` から始まる文字列（例：`-o /etc/passwd`のような文字列）だった場合でも、
  `--`以降はすべて非オプション引数として扱われるため、`say`側のオプションとして誤認識されるリスクを防げる。
  外部入力をコマンドの可変長引数として渡す設計全般で応用できる汎用的なTips。

---

## Frame.io連携（開発用）を作った際の知見（2026-08-12）

### Frame.io API v2とv4はエンドポイント・認証方式が別物。混同して移植すると動かない

Frame.io には v2 API と v4 API が存在し、コメント投稿・アセット取得などのエンドポイントと認証方式が異なる。

| | v2 | v4 |
|---|---|---|
| 認証方式 | 開発者トークンをそのまま`Authorization: Bearer <token>` | Adobe IMS OAuth（`ADOBE_CLIENT_ID`/`ADOBE_CLIENT_SECRET`でトークン発行、Adobeアカウント経由） |
| ベースURL例 | `https://api.frame.io/v2/...` | `https://api.frame.io/v4/accounts/{account_id}/...` |
| account_id | 不要な操作が多い | 多くのエンドポイントで`FRAME_IO_ACCOUNT_ID`が必須 |

v2用に書かれたサンプルコード・過去実装（シンプルなBearerトークン前提）をそのままv4のエンドポイントに移植すると、
認証方式の違い（Adobe OAuthが必要）によりリクエストが通らない。逆にv4のOAuthコードをv2エンドポイントに使うのも誤り。
**移植・参考実装を流用する際は、対象コードがv2向けかv4向けかを必ず先に確認する。**
（本ツールの`server.js`は`FRAME_IO_API_MODE`環境変数でv2/v4を切り替えられる設計になっており、`hasAdobeOAuthConfig()`の有無でv4のOAuth要否を判定している）

### 本番運用中の外部ツールを改修する際は、直接編集せず開発用コピーを別途作って検証する

同僚が本番運用しているFrame.ioアップロードツール（`/Users/fushimi/Documents/Frame.io最新/uploader_tool/`）に
新機能（FlarePocket連携等）を追加する際、本番フォルダを直接編集せず、`Frame.io連携（開発用）/`という
別フォルダに一式コピーして検証する進め方を採用した。
本番の認証情報（`.env`）・編集者マッピング（`destinations.js`の50件超）・チャンネル別Slack設定は
コピーせず、伏見さん専用のテスト値（`destinations.js`は1件のみ）に簡略化してある。
検証が完了した機能だけを、本番データを維持したフルコピーへ改めてマージし、元の同僚経由で本番へ差し替えてもらう想定。
→ 他人が本番運用しているツールを改修する場合の汎用パターンとして、この「開発用コピーを分離してから検証・後でマージ」の
進め方は今後も踏襲する価値がある。

### `destinations.js`のキーは`マネージャー名/チャンネル名/編集者名`の3階層形式が前提

`server.js`の`splitDestinationKey(key)`は`key.split('/')`した結果、
先頭を`managerName`、末尾を`editorName`、間の全部を`channelName`として扱う実装になっている。
そのため`destinations.js`のキーを省略形（例：階層を2つだけにする等）にすると、`channelName`が空文字になったり
`managerName`/`editorName`の対応がずれたりしてパース結果が崩れる。
開発用コピーで新規キーを追加・簡略化する際は、必ず3階層（`マネージャー名/チャンネル名/編集者名`）を維持すること。

---

## 汎用Tips 3点（2026-08-14、初稿受領管理bot・Frame.io連携開発で得た知見）

### Chrome/Chromium headlessでPDF生成する際は`--print-to-pdf-no-header`を付ける

Chrome headlessの`--print-to-pdf`だけを指定すると、日付・URL・ページ番号等の余計なヘッダー・フッターが自動で挿入される。
設計書PDF等、見た目を綺麗に納品したい場合は`--print-to-pdf-no-header`を併用して抑制する。

### `.numbers`ファイルはZip形式。`numbers-parser`（Python）で中身を読み取れる

Appleの`.numbers`ファイルは実体がZipアーカイブで、`numbers-parser`というPythonライブラリで表データを直接読み取れる。
venv経由で`pip install numbers-parser`すれば動作する。ユーザーからNumbersファイルで仕様・データを渡された場合、
手動でCSVに変換してもらう必要がなく、そのまま読み込める。

### 本番`.env`が見当たらず類似名ファイル（`env.txt`等）しかない場合、変数名を伏せて値の一致有無だけを確認する

本番環境の設定ファイルが`.env`という標準名ではなく`env.txt`等の類似名で存在するケースがある。
中身を直接読み上げたりログに出したりすると機密情報（APIキー・トークン等）を露出させるリスクがある。
→ 変数名や値そのものを出力・引用せず、「この変数の値は〇〇と一致していますか？」のように一致有無（Yes/No）だけを
ユーザーに確認してもらう形で調査を進める。機密情報を扱うファイルの中身を調査する際の汎用パターンとして応用できる。

## video-slide-maker PowerPoint準拠UI再構築 Step Fで得た知見（2026-08-19）

### 状態を横断的にガードするbooleanフラグ（`locked`等）は、個別修正ではなく全アクション監査で潰す

「要素をロックする」のような、既存の多数のstore actionを横断してガードが必要になる機能（削除・移動・複製・整列・グループ化・回転…あらゆる変更系操作が対象になりうる）は、
バグ報告のたびに該当アクションだけを場当たり的に直すと「別の操作経路では効いていなかった」という抜け穴が繰り返し発覚しやすい。
video-slide-makerでは`locked`フィールド導入後、3ラウンドにわたって「このアクションだけロックが効いていない」バグが発見され続けた。
→ 2回目・3回目の再発が見えた時点で、個別修正を止めて**store内の全アクションを対象にした網羅監査**（今回は`deckStore.ts`の全53アクションをリストアップし、それぞれ「lockedを考慮すべきか」を1件ずつ判定）に切り替えるべき。
判定基準の例：実データを改変するアクションは原則ガード対象、レイヤー順など「並び」だけを変えデータ自体は変えないものは対象外、
新規追加系（既存要素に触れない）は対象外、ロック状態自体を切り替える操作だけは常に許可（さもないと解除不能になる自己矛盾に陥る）。

### ブラウザ操作ツールが使えない環境での検証は、コードトレース・grep全数調査・ビルド成功どまりであることを明示的に申告する

実ブラウザでのドラッグ・クリック等のUI操作確認（Playwright等）ができない環境では、実装後の検証が「コードを読んで正しいはずと判断した」
「grepで漏れがないか全数チェックした」「`tsc -b`/`npm run build`が通った」という間接的な確認にとどまる。これはビルドが通ることや
静的読解の正しさを保証するが、実際のクリック・ドラッグ操作でUIが意図通り動くことまでは保証しない。
→ 最終GO判定をユーザーに伝える際は「実ブラウザでの目視確認は実施できていない」という検証範囲の限界を必ず明示する。
黙って「検証済み」とだけ伝えると、後で実機動作しない場合にユーザーの信頼を損なう。

---

## Slack Block Kitインタラクティブ機能の実装ハマりポイント（Frame.io連携（開発用）4点セット、2026-08-20）

Slackのボタン・datepicker等インタラクティブ要素を使う機能は、コードレビューだけでは見つからず実チャンネルでのライブテストで初めて発覚するAPI仕様の落とし穴が複数あった。

### `disabled`プロパティはbutton/datepickerで使用不可（`invalid_blocks`エラー）

Slack Block Kitのbutton・datepicker要素に`disabled: true`のようなプロパティを付与すると、Web APIが`invalid_blocks`エラーを返して投稿・更新自体が失敗する。HTMLフォーム要素の感覚で「非活性化すればいい」と実装すると気づかずハマる。
→ 対策：状態に応じて要素を非活性化するのではなく、**ブロックそのものを出し分ける**。操作可能な状態ではinteractiveな`actions`ブロック（button/datepicker）を出し、操作不可・確定済みの状態では同じ位置に静的な`section`テキストブロックを出す設計にする（Frame.io連携（開発用）`server.js`の`buildActionSetBlocks(state)`で採用）。

### `response_url`は30分/5回までしか使えない。ボタン操作後の非同期UI更新には`chat.update`（Bot Token）を使う

Slackのinteraction payloadに含まれる`response_url`は、発行から30分以内・最大5回までしか呼び出せないという制限がある。この制限を超えると、ボタンを押してもエラーは返らず**無言でUI更新が失敗する**（ユーザーからは「反応しない」としか見えないため原因特定が難しい）。
→ 対策：ボタン操作後にメッセージを書き換える処理は`response_url`に頼らず、`chat.update`（`SLACK_BOT_TOKEN`を使ったWeb API呼び出し）で実装する。これなら回数・時間の制限を受けない。

### 教訓

いずれもSlack API仕様のエッジケースであり、コード上は正しく書けているように見えても、実チャンネルでの実運用（特に複数回のボタン往復操作）で初めて発覚する。Slack連携機能を実装する際は、単発のテスト投稿だけでなく「同じメッセージに対して複数回操作する」シナリオを実チャンネルで検証すべき。

---

## Slackメッセージ検知の無限ループ事故（Frame.io連携（開発用）進捗一覧シート連携、2026-08-21）

進捗一覧シート連携機能（Slackメッセージイベントを検知してシートへ行を作成・更新する機能）の実機テスト中、Slackの「fushimi個人用」チャンネルに**124件のスパムメッセージ**が投稿される事故が発生した（全件削除済み。実害はメッセージスパムのみで、シートへの誤書き込みは確認されていない）。

### 原因：Botの投稿検知に使ったIDが「検知対象」と「自分自身の投稿」を区別できていなかった

初稿連絡Bot通知の検知条件が「投稿したBotの`bot_id`が特定の値と一致するか」のみだった。しかしこの`bot_id`は「初稿連絡用Bot」専用の値ではなく、`server.js`自身が同じ`SLACK_BOT_TOKEN`で投稿するあらゆるメッセージ（エラーアラート等）でも同じ値になる。そのため以下の無限ループに陥った。

```
シート書き込み失敗 → エラーアラートをSlackに投稿
  → その投稿自体が「初稿連絡Bot通知」として誤検知される
  → 本文にタイトル・チャンネル情報が無いため解析失敗
  → 失敗を知らせる新たなエラーアラートを投稿
  → 誤検知される…（無限ループ）
```

### 対処（3ラウンドかけて完了）

1. **応急処置**：`INTERNAL_SLACK_POST_MARKER`（ゼロ幅文字 `​‌​`）を追加。サーバー自身がSlackに投稿する全メッセージの文末にこのマーカーを付与し、イベント処理の先頭で「マーカーを含むメッセージは即無視」というガードを最優先で入れた
2. **判定強化**：検知条件を「`bot_id`一致」のみから「`bot_id`一致 AND 本文に初稿連絡Bot通知テンプレート特有の固定文言（『さんから動画が届きました』）を含む」の二重条件に変更。加えて、同一タイトル＋チャンネルで該当行が既に存在する場合は新規追加せずアラートのみで終了する重複防止チェックを追加
3. **見落とし修正**：1回目の対策後もテストゥンの2回目の検証で、`/api/notify`のメイン投稿・フォールバック投稿にマーカー付与が漏れていたことが発覚（この投稿文も『さんから動画が届きました』を含むため新条件にも合致してしまう経路が残っていた）。さらにレビュアンの最終チェックで、4点セット更新（`chat.update`）にもマーカーが無いことが発覚（`message_changed`サブタイプフィルタ1枚のみに依存していた）。両方を修正し、Bot自身が投稿する全経路（`chat.postMessage`5箇所＋`chat.update`1箇所）にマーカー付与を統一した

### 教訓：同じBotトークンを「検知対象」と「自己投稿」の両方に使い回す設計は構造的に事故を再発しやすい

同一のSlack Botトークンを「検知したい通知」と「検知させたくない自分の投稿（アラート・返信等）」の両方に使い回す設計は、**新しい投稿処理を追加するたびに既存の検知ロジックへの影響を全て見直さないと同種の事故が再発するリスクを構造的に抱える**。今回も1回目の対策で塞いだはずの穴が、既存の別の投稿経路（フォールバック投稿・`chat.update`）に潜んでいたことが2回・3回目の検証で判明している。

→ 今回はマーカー方式（自己投稿に目印を付けて除外）で機能したが、これは対症療法。中長期的には以下のような設計変更を検討すべき（今回は未対応・将来の検討事項）：
- アラート専用の別Bot・別Slack Appに分離する（検知対象のBotと物理的に区別する）
- アラート投稿先チャンネルを監視対象から明確に除外する

Slackメッセージ検知機能を実装する際は、「自分（同じアプリ・同じトークン）が投稿する可能性のあるメッセージを、検知ロジックが誤って対象と判定しないか」を実装時点で必ず洗い出す。単発の正常系テストだけでは気づけず、エラー発生時の再帰的な挙動（アラート→誤検知→再アラート）まで含めて実機で検証する必要がある。
