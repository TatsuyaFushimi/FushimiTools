# Premiere Pro エクステンション 開発仕様書

## 概要

Adobe Premiere Pro 内で動作するパネル型エクステンション。  
**Google Drive に置いたモーショングラフィックテンプレート（.mogrt）をパネルから直接 Premiere に読み込める**ようにする。  
社内向け `.ccx` ファイル配布。

- **AI必要**: なし
- **配布方法**: `.ccx` ファイルを共有 → 手動インストール
- **対象バージョン**: Premiere Pro 2022（v22.0）以降

### ユーザー体験イメージ

```
1. Premiere でパネルを開く
2. Drive 上の mogrt 一覧が自動表示される
3. 使いたいテンプレートをクリック
4. 自動ダウンロード → プロジェクトに取り込まれる
5. タイムラインに配置して使う
```

**Drive フォルダに mogrt を追加するだけで全員に即反映される。**

---

## 方式決定：UXP を採用

| 方式 | 概要 | 採用 |
|------|------|------|
| **UXP** | 2022以降の新方式。HTML/CSS/JS。公式推奨 | ✅ |
| CEP | 旧方式。まだ動くが将来的に廃止予定 | ❌ |

---

## 開発環境セットアップ（初回のみ）

### 必要ツール

```bash
# Node.js（インストール済みなら不要）
brew install node

# UXP CLI（パッケージ化に使用）
npm install -g @adobe/uxp-cli
```

### Adobe UXP Developer Tools

1. Creative Cloud アプリを開く
2. 「UXP Developer Tool」を検索してインストール
3. 起動すると開発中のプラグインをロードできる

---

## フォルダ構成

```
premiere-extension/
├── manifest.json      ← 必須・プラグイン定義
├── index.html         ← UI本体
├── main.js            ← ロジック
├── styles.css
└── icons/
    └── icon.png       ← 23×23px
```

---

## manifest.json テンプレート

```json
{
  "manifestVersion": 7,
  "id": "com.busoken.premiere-extension",
  "name": "Fushimi Tools - Premiere",
  "version": "1.0.0",
  "host": {
    "app": "PPRO",
    "minVersion": "22.0"
  },
  "entrypoints": [
    {
      "type": "panel",
      "id": "mainPanel",
      "label": { "default": "Fushimi Tools" },
      "minimumSize": { "width": 300, "height": 400 },
      "preferredDockedSize": { "width": 320, "height": 500 }
    }
  ]
}
```

> `id` は全世界でユニークである必要がある（逆ドメイン形式）。`com.busoken.*` を使えばOK。

---

## 開発フロー

```
1. フォルダ作成（上記構成）
2. UXP Developer Tools で「Add Plugin」→ manifest.json を選択
3. 「Load」→ Premiere Pro が開いてパネルが表示される
4. HTML/JS を編集 → Developer Tools で「Reload」して確認
5. 完成したら ccx にパッケージ化 → 配布
```

---

## 主要 API（よく使うもの）

```javascript
// アクティブなプロジェクト
const project = app.project;

// ルートビン（プロジェクトパネルの最上位フォルダ）
const rootItem = project.rootItem;

// 新しいビン（フォルダ）を作成
rootItem.createBin("フォルダ名");

// 子アイテム一覧
for (let i = 0; i < rootItem.children.numItems; i++) {
  const item = rootItem.children[i];
  console.log(item.name);
}

// アクティブなシーケンス
const seq = project.activeSequence;
console.log(seq.name);
```

詳細: [UXP API リファレンス（Premiere）](https://developer.adobe.com/premiere-pro/uxp/ppro_reference/api/)

---

## パッケージ化・配布手順

### パッケージ化

```bash
cd premiere-extension/

# ccx ファイルを生成
uxp plugin package
# → ./dist/com.busoken.premiere-extension.ccx が生成される
```

### 社内配布・インストール手順（受け取る側）

1. `.ccx` ファイルを受け取る
2. **ダブルクリック** → Creative Cloud がインストールを実行
3. Premiere Pro を再起動
4. メニュー「ウィンドウ」→「エクステンション」→ ツール名を選択

> Creative Cloud がインストールされていれば追加ソフト不要。

---

## デバッグ方法

- UXP Developer Tools の「Logs」タブでコンソールログを確認
- `console.log()` が使える
- Premiere Pro のクラッシュは manifest.json の記述ミスが多い

---

## 注意事項

- Premiere Pro が **起動中** でないとプラグインをロードできない
- manifest.json の `id` は一度決めたら変えない（再インストールが必要になる）
- アイコンなしでも動作するが、パネル識別に便利なので用意推奨
- UXP は ES2020 対応。`async/await`・`fetch` が使える

---

## Google Drive 連携（mogrt テンプレート配信）

### 認証方式：サービスアカウント（確定）

| 方式 | 概要 | 採用 |
|------|------|------|
| **サービスアカウント** | Google が発行する専用アカウントで Drive を読み取り。ユーザーログイン不要 | ✅ |
| OAuth 2.0 | ユーザーが Google ログイン | ❌ デスクトップUXPでは実装が複雑 |
| 公開共有リンク | API キーのみ。誰でもアクセス可 | ❌ 社内ファイル向けに不向き |

### セットアップ手順（開発時・初回のみ）

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクト作成
2. 「Google Drive API」を有効化
3. 「サービスアカウント」を作成 → JSON キーをダウンロード
4. 社内の Google Drive フォルダを作成し、サービスアカウントのメールアドレスを **閲覧者** として共有
5. JSON キーの内容をエクステンションの設定ファイルに埋め込む（またはRender等のバックエンド経由）

### Drive API 呼び出しの流れ

```javascript
// 1. アクセストークン取得（サービスアカウントのJWTを使って）
const token = await getServiceAccountToken(credentials);

// 2. フォルダ内の mogrt 一覧を取得
const folderId = 'YOUR_DRIVE_FOLDER_ID';
const res = await fetch(
  `https://www.googleapis.com/drive/v3/files?q='${folderId}'+in+parents+and+name+contains+'.mogrt'&fields=files(id,name,modifiedTime)`,
  { headers: { Authorization: `Bearer ${token}` } }
);
const { files } = await res.json();

// 3. ファイルをダウンロード
const fileRes = await fetch(
  `https://www.googleapis.com/drive/v3/files/${fileId}?alt=media`,
  { headers: { Authorization: `Bearer ${token}` } }
);
const buffer = await fileRes.arrayBuffer();

// 4. ローカルに保存（UXP localFileSystem API）
const folder = await fs.getTemporaryFolder();
const file = await folder.createFile('template.mogrt', { overwrite: true });
await file.write(buffer);

// 5. Premiere に取り込む
app.project.importFiles([file.nativePath]);
```

### Drive フォルダ管理ルール（運用）

| ルール | 内容 |
|--------|------|
| フォルダ構成 | Drive 内に `mogrt/` フォルダを1つ作成。カテゴリはサブフォルダで管理 |
| ファイル命名 | `[カテゴリ]_[テンプレート名].mogrt`（例: `title_opening-A.mogrt`） |
| 更新方法 | Drive フォルダにファイルを追加・削除するだけ。エクステンション側は自動反映 |
| アクセス権 | サービスアカウントのみ閲覧権限。社員は Drive への直アクセス不要 |

### キーの管理方法（要検討）

サービスアカウントの JSON キーは機密情報なので下記のいずれかで管理する：

- **A. エクステンション内に直埋め込み**：簡単だが ccx ファイルを解凍すると見える。社内配布のみなら許容範囲
- **B. Render 等のバックエンド経由**：エクステンション → 自社サーバー → Drive API。キーが外に出ない。推奨

---

---

## 初回セットアップ（開発・テスト手順）

### 1. Google API キーを取得する

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクト作成 or 既存を選択
3. 「APIとサービス」→「ライブラリ」→ **「Google Drive API」** を有効化
4. 「認証情報」→「認証情報を作成」→ **「APIキー」**
5. 発行されたキー（`AIza...`）をコピー
6. 「APIキーを制限」→ Drive API のみに制限（推奨）

### 2. Drive フォルダの共有設定

1. 素材を入れる Google Drive フォルダを作成
2. 右クリック →「共有」→「リンクをコピー」
3. 共有設定を **「リンクを知っている全員が閲覧可」** に変更

### 3. UXP Developer Tools でロード（開発中）

1. Creative Cloud → **「UXP Developer Tool」** を起動
2. 「Add Plugin」→ `premiere-extension/manifest.json` を選択
3. Premiere Pro を起動した状態で「Load」
4. メニュー「ウィンドウ」→「エクステンション」→「Drive Asset Browser」

### 4. パネルの使い方

1. ⚙ ボタンを押して API キーを入力 →「保存」
2. Drive フォルダの共有 URL を貼り付け →「読み込む」
3. ファイルがサムネイル付きで一覧表示される
4. クリックで自動ダウンロード → Premiere プロジェクトに追加

---

## 今後の作業

- [ ] Premiere Pro 上で実機テスト・動作確認
- [ ] パッケージ化（`uxp plugin package` → `.ccx`）
- [ ] 社内配布用インストールマニュアル作成
- [ ] 必要に応じて機能追加（フォルダ絞り込み・検索など）
