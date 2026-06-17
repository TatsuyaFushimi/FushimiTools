// Premiere Pro にファイルを取り込む
function importFileToProject(filePath) {
  try {
    app.project.importFiles([filePath], true, app.project.rootItem, false);
    return JSON.stringify({ ok: true });
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}
