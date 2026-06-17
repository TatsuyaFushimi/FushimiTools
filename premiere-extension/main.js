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

// ─── ArrayBuffer → Base64 変換 ───────────────────────────
function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunk = 8192;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
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
// フォルダ階層スタック: [{ id, name }, ...]
let folderStack = [];

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
  folderStack = [{ id: folderId, name: 'ルート' }];
  await loadFolder(folderId);
}

async function loadFolder(folderId) {
  showStatus('読み込み中...', 'loading');
  document.getElementById('file-grid').innerHTML = '';
  renderBreadcrumb();

  try {
    const files = await fetchDriveFiles(folderId);
    currentFiles = files;
    renderFiles(files);
    showStatus(`${files.length} 件`, 'info');
    if (files.length === 0) showStatus('ファイルがありません', 'info');
  } catch (e) {
    showStatus(`エラー: ${e.message}`, 'error');
  }
}

async function fetchDriveFiles(folderId) {
  const fields = 'files(id,name,mimeType,size,modifiedTime)';
  const q = encodeURIComponent(`'${folderId}' in parents and trashed=false`);
  const url = `https://www.googleapis.com/drive/v3/files?q=${q}&key=${apiKey}&fields=${fields}&pageSize=200&orderBy=folder,name`;

  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error?.message || `APIエラー (${res.status})`);
  }
  const data = await res.json();
  return data.files || [];
}

// ─── パンくず ─────────────────────────────────────────────
function renderBreadcrumb() {
  const el = document.getElementById('breadcrumb');
  if (folderStack.length <= 1) {
    el.classList.add('hidden');
    return;
  }
  el.classList.remove('hidden');
  el.innerHTML = folderStack.map((f, i) => {
    if (i === folderStack.length - 1) {
      return `<span class="bc-current">${escHtml(f.name)}</span>`;
    }
    return `<span class="bc-link" onclick="navigateTo(${i})">${escHtml(f.name)}</span><span class="bc-sep">›</span>`;
  }).join('');
}

async function navigateTo(index) {
  folderStack = folderStack.slice(0, index + 1);
  await loadFolder(folderStack[folderStack.length - 1].id);
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

    const isDraggable = info.canImport && info.type !== 'folder';
    return `
      <div class="file-card" data-index="${i}"
           onclick="importFile(${i})"
           ${isDraggable ? `draggable="true" ondragstart="handleDragStart(event,${i})"` : ''}>
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

// ─── ファイルダウンロード共通処理 ────────────────────────
async function downloadFileToTemp(file) {
  const downloadUrl =
    `https://www.googleapis.com/drive/v3/files/${file.id}?alt=media&key=${apiKey}`;
  const res = await fetch(downloadUrl);
  if (!res.ok) throw new Error(`ダウンロード失敗 (${res.status})`);

  const buffer = await res.arrayBuffer();
  const safeName = file.name.replace(/[/\\?%*:|"<>]/g, '_');
  const filePath = '/private/tmp/' + safeName;
  const base64 = arrayBufferToBase64(buffer);
  const writeResult = window.cep.fs.writeFile(filePath, base64, "base64");
  if (writeResult.err !== 0) throw new Error('ファイル保存失敗: ' + (writeResult.desc || writeResult.err));
  return filePath;
}

// ─── クリック：フォルダ移動 or プロジェクトに追加 ──────────
async function importFile(index) {
  const file = currentFiles[index];
  const info = getFileInfo(file);

  if (info.type === 'folder') {
    folderStack.push({ id: file.id, name: file.name });
    await loadFolder(file.id);
    return;
  }
  if (!info.canImport) return;

  const card = document.querySelector(`.file-card[data-index="${index}"]`);
  card.classList.add('importing');
  showStatus(`取り込み中: ${file.name}`, 'loading');

  try {
    const filePath = await downloadFileToTemp(file);
    const safePath = filePath.replace(/'/g, "\\'");
    const result = await evalScript(`importFileToProject('${safePath}')`);
    const parsed = JSON.parse(result);
    if (parsed.error) throw new Error(parsed.error);

    card.classList.remove('importing');
    card.classList.add('imported');
    showStatus('✓ プロジェクトに追加しました', 'success');
    setTimeout(hideStatus, 2500);
  } catch (e) {
    card.classList.remove('importing');
    showStatus(`エラー: ${e.message}`, 'error');
  }
}

// ─── ドラッグ&ドロップ ────────────────────────────────────
let lastMouseEvent = null;
document.addEventListener('mousedown', e => { lastMouseEvent = e; });

async function handleDragStart(event, index) {
  event.preventDefault();
  const file = currentFiles[index];
  const info = getFileInfo(file);
  if (!info.canImport || info.type === 'folder') return;

  showStatus(`ドラッグ準備中: ${file.name}`, 'loading');
  try {
    const filePath = await downloadFileToTemp(file);
    hideStatus();
    if (window.cep && window.cep.dnd && lastMouseEvent) {
      window.cep.dnd.initiateDrag(lastMouseEvent, [filePath], ['']);
    }
  } catch (e) {
    showStatus(`エラー: ${e.message}`, 'error');
  }
}
