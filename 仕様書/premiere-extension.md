# Premiere Pro エクステンション 開発仕様書

## 概要

Adobe Premiere Pro 内で動作するパネル型エクステンション。  
社内向け `.ccx` ファイル配布。機能内容は未定（随時更新）。

- **AI必要**: 機能次第（基本不要）
- **配布方法**: `.ccx` ファイルを共有 → 手動インストール
- **対象バージョン**: Premiere Pro 2022（v22.0）以降

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

## 今後追加する項目

- [ ] 機能確定後：機能仕様・画面設計
- [ ] インストールマニュアル（社内向け）
- [ ] バージョン管理ルール
