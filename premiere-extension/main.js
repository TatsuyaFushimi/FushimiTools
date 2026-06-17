// ─── ExtendScript ブリッジ ────────────────────────────────
function evalScript(script) {
  return new Promise((resolve) => {
    if (!window.__adobe_cep__) {
      resolve(JSON.stringify({ error: 'CEP bridge not available' }));
      return;
    }
    window.__adobe_cep__.evalScript(script, resolve);
  });
}

// ─── Node.js モジュール（importFile 時のみ使用）─────────────
function getNodeModules() {
  try {
    return {
      fs: require('fs'),
      os: require('os'),
      path: require('path'),
    };
  } catch (e) {
    throw new Error('ファイル保存に失敗しました（Node.js 利用不可）: ' + e.message);
  }
}

// ─── ファイル種別判定 ─────────────────────────────────────
function getFileInfo(file) {
  const name = (file.name || '').toLowerCase();
  const mime = file.mimeType || '';

  if (name.endsWith('.mogrt'))
    return { type: 'mogrt', icon: '✨', label: 'MOGRT', canImport: true };
  if (mime.startsWith('image/') || /\.(jpg|jpeg|png|gif|webp|bmp|tiff|psd|ai|eps)$/.test(name))
    return { type: 'image', icon: '🖼', label: 'IMAGE', canImport: true };
  if (mime.startsWith('video/') || /\.(mp4|mov|avi|mkv|wmv|flv|m4v|mxf|r3d|braw)$/.test(name))
    return { type: 'video', icon: '🎬', label: 'VIDEO', canImport: true };
  if (mime.startsWith('audio/') || /\.(mp3|wav|aac|flac|aif|aiff)$/.test(name))
    return { type: 'audio', icon: '🎵', label: 'AUDIO', canImport: true };
  if (mime === 'application/vnd.google-apps.folder')
    return { type: 'folder', icon: '📁', label: 'FOLDER', canImport: false };

  return { type: 'other', icon: '📄', label: 'FILE', canImport: true };
}

function extractFolderId(url) {
  const match = url.match(/\/folders\/([a-zA-Z0-9_-]+)/);
  return match ? match[1] : null;
}

function formatSize(bytes) {
  if (!bytes || isNaN(bytes)) return '';
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / 1048576).toFixed(1)}MB`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── 状態 ────────────────────────────────────────────────
let apiKey = '';
let currentFiles = [];

// ─── 初期化 ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  apiKey = localStorage.getItem('drive_api_key') || '';
  document.getElementById('api-key').value = apiKey;

  const savedUrl = localStorage.getItem('drive_folder_url') || '';
  if (savedUrl) document.getElementById('folder-url').value = savedUrl;

  document.getElementById('settings-toggle').addEventListener('click', toggleSettings);
  document.getElementById('save-settings').addEventListener('click', saveSettings);
  document.getElementById('load-btn').addEventListener('click', loadFiles);
  document.getElementById('folder-url').addEventListener('keydown', e => {
    if (e.key === 'Enter') loadFiles();
  });

  if (!apiKey) toggleSettings();
});

// ─── 設定 ────────────────────────────────────────────────
function toggleSettings() {
  document.getElementById('settings-panel').classList.toggle('hidden');
}

function saveSettings() {
  apiKey = document.getElementById('api-key').value.trim();
  localStorage.setItem('drive_api_key', apiKey);
  showStatus('設定を保存しました', 'success');
  setTimeout(() => {
    document.getElementById('settings-panel').classList.add('hidden');
    hideStatus();
  }, 1000);
}

// ─── ステータス ──────────────────────────────────────────
function showStatus(msg, type = 'info') {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className = `status ${type}`;
}

function hideStatus() {
  document.getElementById('status').className = 'status hidden';
}

// ─── ファイル読み込み ────────────────────────────────────
async function loadFiles() {
  const urlInput = document.getElementById('folder-url').value.trim();
  if (!urlInput) return showStatus('URLを入力してください', 'error');
  if (!apiKey) return showStatus('⚙ から Google API キーを設定してください', 'error');

  const folderId = extractFolderId(urlInput);
  if (!folderId) return showStatus('正しい Google Drive フォルダURLを入力してください', 'error');

  localStorage.setItem('drive_folder_url', urlInput);
  showStatus('読み込み中...', 'loading');
  document.getElementById('file-grid').innerHTML = '';

  try {
    const files = await fetchDriveFiles(folderId);
    currentFiles = files;
    renderFiles(files);
    if (files.length === 0) {
      showStatus('ファイルが見つかりませんでした', 'info');
    } else {
      showStatus(`${files.length} 件`, 'info');
    }
  } catch (e) {
    showStatus(`エラー: ${e.message}`, 'error');
  }
}

async function fetchDriveFiles(folderId) {
  const fields = 'files(id,name,mimeType,size,modifiedTime)';
  const q = encodeURIComponent(`'${folderId}' in parents and trashed=false`);
  const url = `https://www.googleapis.com/drive/v3/files?q=${q}&key=${apiKey}&fields=${fields}&pageSize=200&orderBy=name`;

  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error?.message || `APIエラー (${res.status})`);
  }
  const data = await res.json();
  return (data.files || []).filter(f => getFileInfo(f).type !== 'folder');
}

// ─── 描画 ─────────────────────────────────────────────────
function renderFiles(files) {
  const grid = document.getElementById('file-grid');

  if (files.length === 0) {
    grid.innerHTML = '<div class="empty">ファイルがありません</div>';
    return;
  }

  grid.innerHTML = files.map((file, i) => {
    const info = getFileInfo(file);
    const hasThumbnail = info.type === 'image' || info.type === 'video';
    const thumbUrl = hasThumbnail
      ? `https://drive.google.com/thumbnail?id=${file.id}&sz=w220`
      : null;

    return `
      <div class="file-card" data-index="${i}" onclick="importFile(${i})">
        <div class="thumb">
          ${thumbUrl
            ? `<img src="${thumbUrl}"
                    onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"
                    alt="">
               <div class="thumb-icon" style="display:none">${info.icon}</div>`
            : `<div class="thumb-icon">${info.icon}</div>`
          }
          <span class="type-badge">${info.label}</span>
        </div>
        <div class="file-name" title="${escHtml(file.name)}">${escHtml(file.name)}</div>
        <div class="file-size">${formatSize(parseInt(file.size))}</div>
      </div>
    `;
  }).join('');
}

// ─── Premiere Pro に取り込み ──────────────────────────────
async function importFile(index) {
  const file = currentFiles[index];
  const info = getFileInfo(file);
  if (!info.canImport) return;

  const card = document.querySelector(`.file-card[data-index="${index}"]`);
  card.classList.add('importing');
  showStatus(`ダウンロード中: ${file.name}`, 'loading');

  try {
    // Drive からダウンロード
    const downloadUrl =
      `https://www.googleapis.com/drive/v3/files/${file.id}?alt=media&key=${apiKey}`;
    const res = await fetch(downloadUrl);
    if (!res.ok) throw new Error(`ダウンロード失敗 (${res.status})`);

    const buffer = await res.arrayBuffer();
    const bytes = new Uint8Array(buffer);

    // 一時ディレクトリに保存（Node.js fs）
    const { fs: nodefs, os, path: nodepath } = getNodeModules();
    const tempDir = os.tmpdir();
    const filePath = nodepath.join(tempDir, file.name);
    nodefs.writeFileSync(filePath, Buffer.from(bytes));

    // ExtendScript 経由で Premiere Pro に取り込み
    const safePath = filePath.replace(/\\/g, '/').replace(/'/g, "\\'");
    const result = await evalScript(`importFileToProject('${safePath}')`);
    const parsed = JSON.parse(result);
    if (parsed.error) throw new Error(parsed.error);

    card.classList.remove('importing');
    card.classList.add('imported');
    showStatus(`✓ プロジェクトに追加しました`, 'success');
    setTimeout(hideStatus, 2500);
  } catch (e) {
    card.classList.remove('importing');
    showStatus(`エラー: ${e.message}`, 'error');
  }
}
