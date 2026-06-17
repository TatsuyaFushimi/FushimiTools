// Premiere Pro にファイルを取り込む
function importFileToProject(filePath) {
  try {
    var f = new File(filePath);
    if (!f.exists) {
      return JSON.stringify({ error: 'ファイルが見つかりません: ' + filePath });
    }
    app.project.importFiles([f.fsName], true, app.project.rootItem, false);
    return JSON.stringify({ ok: true });
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}
