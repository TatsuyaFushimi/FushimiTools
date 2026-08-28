import os
import json
import shutil
import tempfile
import threading
import time
import uuid
import hashlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone

import requests
from flask import Flask, render_template, request, jsonify, send_file, after_this_request

app = Flask(__name__)

jobs = {}
jobs_lock = threading.Lock()

TMP_PREFIX = 'ytdl_job_'
JOB_TIMEOUT_SECONDS = 20 * 60          # ジョブ自体のタイムアウト
STALE_DIR_MAX_AGE_SECONDS = 30 * 60    # 完了/失敗から30分経過した一時ディレクトリは掃除
SWEEP_INTERVAL_SECONDS = 10 * 60       # 一時ディレクトリの全体掃除間隔
TIMEOUT_CHECK_INTERVAL_SECONDS = 60    # ジョブタイムアウトのチェック間隔

SPREADSHEET_ID = '1JJXJ5NWiCm5ZmnNKdhzmglD3xGwelkeswtAfJg95yUY'
SHEET_NAME = 'ログ'

# 通常解像度(1080p以下)は1、4K(2160p以上)を含む場合は2消費。総枠は2。
# → 1080p以下なら最大2本同時、4Kが絡む場合はそれだけで枠を使い切る。
DOWNLOAD_PERMITS = 2

executor = ThreadPoolExecutor(max_workers=4)

_sheets_service_cache = None


class WeightedSemaphore:
    """指定した重みを一度に確保する疑似セマフォ。
    threading.Semaphore.acquire()を重み回数呼ぶ方式だと、複数スレッドが
    部分的に確保し合ってデッドロックしうるため、Conditionで原子的に確保する。
    """

    def __init__(self, total):
        self._total = total
        self._used = 0
        self._cond = threading.Condition()

    def acquire(self, weight):
        with self._cond:
            while self._used + weight > self._total:
                self._cond.wait()
            self._used += weight

    def release(self, weight):
        with self._cond:
            self._used -= weight
            self._cond.notify_all()


download_semaphore = WeightedSemaphore(DOWNLOAD_PERMITS)


@app.before_request
def _verify_worker_secret():
    if request.path == '/healthz':
        return None
    expected = os.environ.get('WORKER_SHARED_SECRET', '')
    provided = request.headers.get('X-Worker-Secret', '')
    if not expected or provided != expected:
        return jsonify({'error': 'forbidden'}), 403


def _get_user_email():
    return request.headers.get('X-User-Email', '').strip()


def _user_id_from_email(email):
    return hashlib.sha256(email.encode('utf-8')).hexdigest()[:16]


SHARED_COOKIE_KV_KEY = 'shared_cookie'
SHARED_COOKIE_CACHE_TTL_SECONDS = 5 * 60  # ダウンロードのたびにCloudflare APIを叩かないようにキャッシュする

_shared_cookie_cache = {'value': '', 'fetched_at': 0.0}
_shared_cookie_cache_lock = threading.Lock()


def _fetch_shared_cookie_from_kv():
    account_id = os.environ.get('CF_ACCOUNT_ID')
    namespace_id = os.environ.get('CF_KV_NAMESPACE_ID')
    api_token = os.environ.get('CF_API_TOKEN')
    if not (account_id and namespace_id and api_token):
        return ''

    url = (
        f'https://api.cloudflare.com/client/v4/accounts/{account_id}'
        f'/storage/kv/namespaces/{namespace_id}/values/{SHARED_COOKIE_KV_KEY}'
    )
    try:
        res = requests.get(url, headers={'Authorization': f'Bearer {api_token}'}, timeout=10)
        res.raise_for_status()
        return res.text
    except Exception as e:
        # KV取得失敗でもダウンロード機能全体は止めない(Cookie無しで継続)
        print(f'[shared_cookie] KVからの取得に失敗しました: {e}')
        return ''


def _get_shared_cookie():
    """Cloudflare KVから共有Cookieを取得する。直近の取得結果を5分間キャッシュし、
    ダウンロードのたびにCloudflare APIを叩かないようにする(マルチスレッド動作のためLockで保護)。
    """
    now = time.time()
    with _shared_cookie_cache_lock:
        if now - _shared_cookie_cache['fetched_at'] < SHARED_COOKIE_CACHE_TTL_SECONDS:
            return _shared_cookie_cache['value']

    value = _fetch_shared_cookie_from_kv()

    with _shared_cookie_cache_lock:
        _shared_cookie_cache['value'] = value
        _shared_cookie_cache['fetched_at'] = now
    return value


@contextmanager
def _cookie_file_from_header():
    """共有Cookieの内容をリクエストごとの一時ファイルに書き出す。
    Cookieが空/未取得ならNoneを返し、Cookie無しでyt-dlpを実行させる。
    """
    cookie_content = _get_shared_cookie()
    if not cookie_content:
        yield None
        return
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
    try:
        tmp.write(cookie_content)
        tmp.close()
        yield tmp.name
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def _ffmpeg_location():
    for path in ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']:
        if os.path.exists(path):
            return os.path.dirname(path)
    found = shutil.which('ffmpeg')
    return os.path.dirname(found) if found else None


def _ydl_opts_base(cookie_path=None):
    opts = {'quiet': True, 'no_warnings': True}
    if cookie_path:
        opts['cookiefile'] = cookie_path
    loc = _ffmpeg_location()
    if loc:
        opts['ffmpeg_location'] = loc
    return opts


def _is_bot_error(msg: str) -> bool:
    return 'Sign in to confirm' in msg or 'bot' in msg.lower()


def _parse_quality(quality):
    """quality文字列を高さ(px)に変換。未指定/bestならNone(最高画質自動)"""
    if not quality:
        return None
    q = str(quality).strip().lower()
    if q in ('best', 'auto', ''):
        return None
    if q in ('4k', '2160p', '2160'):
        return 2160
    digits = ''.join(ch for ch in q if ch.isdigit())
    return int(digits) if digits else None


def _release_once(job):
    with job['release_lock']:
        if not job.get('sem_released'):
            job['sem_released'] = True
            download_semaphore.release(job['weight'])


def _get_sheets_service():
    global _sheets_service_cache
    if _sheets_service_cache is not None:
        return _sheets_service_cache

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_info = None
    json_str = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    if json_str:
        creds_info = json.loads(json_str)
    else:
        # ローカルテスト用フォールバック(Renderでは環境変数を使う)
        local_candidate = os.path.join(
            os.path.dirname(__file__), '..', 'fushimiqr-7ac92df75bf6.json'
        )
        if os.path.exists(local_candidate):
            with open(local_candidate) as f:
                creds_info = json.load(f)

    if not creds_info:
        raise RuntimeError('Google service account credentials not found')

    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    _sheets_service_cache = service
    return service


def _log_download_to_sheet(user_email, video_url, title):
    try:
        service = _get_sheets_service()
        timestamp = datetime.now(timezone.utc).isoformat()
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{SHEET_NAME}!A:D',
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body={'values': [[timestamp, user_email, video_url, title]]},
        ).execute()
    except Exception as e:
        print(f'[sheets] ログ記録に失敗しました: {e}')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/healthz')
def healthz():
    return jsonify({'ok': True})


@app.route('/api/info', methods=['POST'])
def get_info():
    user_email = _get_user_email()
    if not user_email:
        return jsonify({'error': 'X-User-Emailヘッダーが必要です'}), 400

    try:
        import yt_dlp
        url = (request.json or {}).get('url', '').strip()
        if not url:
            return jsonify({'error': 'URLを入力してください'}), 400

        with _cookie_file_from_header() as cookie_path:
            with yt_dlp.YoutubeDL(_ydl_opts_base(cookie_path)) as ydl:
                info = ydl.extract_info(url, download=False)

        resolutions = set()
        for f in info.get('formats', []):
            h = f.get('height')
            if h and f.get('vcodec', 'none') != 'none':
                resolutions.add(h)

        dur = int(info.get('duration') or 0)
        h, m, s = dur // 3600, (dur % 3600) // 60, dur % 60
        duration_str = f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'

        return jsonify({
            'title': info.get('title', ''),
            'thumbnail': info.get('thumbnail', ''),
            'duration': duration_str,
            'uploader': info.get('uploader', ''),
            'resolutions': sorted(resolutions, reverse=True),
        })

    except Exception as e:
        msg = str(e)
        if _is_bot_error(msg):
            return jsonify({'error': 'BOT_DETECTION', 'message': msg}), 400
        return jsonify({'error': msg}), 400


@app.route('/api/download', methods=['POST'])
def start_download():
    user_email = _get_user_email()
    if not user_email:
        return jsonify({'error': 'X-User-Emailヘッダーが必要です'}), 400
    user_id = _user_id_from_email(user_email)

    data = request.json or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URLを入力してください'}), 400
    quality = data.get('quality')
    height = _parse_quality(quality)
    weight = 2 if height and height >= 2160 else 1

    job_id = str(uuid.uuid4())
    job = {
        'status': 'queued',
        'progress': 0,
        'speed': '',
        'eta': '',
        'weight': weight,
        'sem_released': False,
        'release_lock': threading.Lock(),
        'created_at': time.time(),
        'user_id': user_id,
        'user_email': user_email,
        'video_url': url,
    }
    with jobs_lock:
        jobs[job_id] = job

    # _do_downloadはリクエストコンテキスト外のスレッドで動くため、
    # Cookie内容はここ(リクエストコンテキスト内)で読み取って渡す
    cookie_content = _get_shared_cookie()
    executor.submit(_do_download, job_id, url, height, weight, user_id, cookie_content)

    return jsonify({'job_id': job_id})


def _do_download(job_id, url, height, weight, user_id, cookie_content):
    import yt_dlp

    job = jobs[job_id]

    # 総枠(2)を超える場合はここでブロックされ順番待ちになる
    download_semaphore.acquire(weight)

    job['status'] = 'downloading'
    job['started_at'] = time.time()

    # job_idは既にuuid4で一意なため、mkdtempのランダムサフィックスは使わず
    # ディレクトリ名をジョブIDから一意に復元できる形にしておく
    # (mkdtempの既定ランダムサフィックスは'_'を含みうるため、掃除スレッドでの
    #  ジョブID逆算がずれるのを避ける)
    tmpdir = os.path.join(tempfile.gettempdir(), f'{TMP_PREFIX}{job_id}')

    # tmpdir配下に置くことで、成功/失敗いずれの経路のshutil.rmtree(tmpdir)でも一緒に消える
    cookie_path = os.path.join(tmpdir, 'cookies.txt') if cookie_content else None

    # h264(avc1)を優先 → QuickTime互換。なければVP9等にフォールバック
    if not height:
        fmt = (
            'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/'
            'bestvideo[vcodec^=avc1]+bestaudio/'
            'bestvideo+bestaudio/best'
        )
    else:
        fmt = (
            f'bestvideo[vcodec^=avc1][height<={height}]+bestaudio[acodec^=mp4a]/'
            f'bestvideo[vcodec^=avc1][height<={height}]+bestaudio/'
            f'bestvideo[height<={height}]+bestaudio/'
            f'best[height<={height}]/best'
        )

    def progress_hook(d):
        current = jobs.get(job_id)
        if not current:
            return
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            current['progress'] = round(downloaded / total * 100) if total else 0
            current['speed'] = (d.get('_speed_str') or '').strip()
            current['eta'] = (d.get('_eta_str') or '').strip()
        elif d['status'] == 'finished':
            current['progress'] = 99
            current['eta'] = 'マージ中...'

    opts = {
        **_ydl_opts_base(cookie_path),
        'format': fmt,
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'progress_hooks': [progress_hook],
    }

    try:
        # makedirsとCookie書き込みもセマフォ確保後の処理なので、ここ(try)の中で行い
        # 例外発生時にfinallyでセマフォが確実に解放されるようにする
        os.makedirs(tmpdir, exist_ok=True)
        job['tmpdir'] = tmpdir
        if cookie_content:
            with open(cookie_path, 'w', encoding='utf-8') as f:
                f.write(cookie_content)

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            expected = ydl.prepare_filename(info)

        base = os.path.splitext(expected)[0]
        mp4_path = base + '.mp4'

        if not os.path.exists(mp4_path):
            for fname in os.listdir(tmpdir):
                if fname.endswith('.mp4'):
                    mp4_path = os.path.join(tmpdir, fname)
                    break

        current = jobs.get(job_id)
        if current is None or current.get('status') != 'downloading':
            # タイムアウト等で既に失敗扱いになっている → 結果は破棄してクリーンアップのみ
            shutil.rmtree(tmpdir, ignore_errors=True)
            return

        title = info.get('title', '')
        current.update({
            'status': 'done',
            'filepath': mp4_path,
            'filename': os.path.basename(mp4_path),
            'progress': 100,
            'eta': '',
            'title': title,
            'completed_at': time.time(),
        })

        _log_download_to_sheet(current['user_email'], url, title)

    except Exception as e:
        msg = str(e)
        current = jobs.get(job_id)
        if current is not None and current.get('status') == 'downloading':
            current.update({
                'status': 'error',
                'error': msg,
                'bot_error': _is_bot_error(msg),
                'completed_at': time.time(),
            })
        shutil.rmtree(tmpdir, ignore_errors=True)

    finally:
        _release_once(job)


@app.route('/api/progress/<job_id>')
def get_progress(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'ジョブが見つかりません'}), 404
    if job.get('user_id') != _user_id_from_email(_get_user_email()):
        return jsonify({'error': '他のユーザーのジョブにはアクセスできません'}), 403
    # release_lock等の内部フィールドは返さない
    safe_keys = ('status', 'progress', 'speed', 'eta', 'error', 'bot_error', 'filename', 'title')
    return jsonify({k: job[k] for k in safe_keys if k in job})


@app.route('/api/file/<job_id>')
def serve_file(job_id):
    # 同一job_idへの連打で2リクエストが同じjobを取得しクリーンアップと競合するのを防ぐため、
    # 権限確認まで済ませた上でここで即座にpopする(以降の同じjob_idへのリクエストは404になる)
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job.get('status') != 'done':
            return 'ファイルの準備ができていません', 404
        if job.get('user_id') != _user_id_from_email(_get_user_email()):
            return '他のユーザーのジョブにはアクセスできません', 403
        jobs.pop(job_id, None)

    filepath = job['filepath']
    tmpdir = job.get('tmpdir') or os.path.dirname(filepath)

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
        return response

    return send_file(filepath, as_attachment=True, download_name=job['filename'])


def _check_job_timeouts(now):
    with jobs_lock:
        snapshot = list(jobs.items())
    for job_id, job in snapshot:
        if job.get('status') != 'downloading':
            continue
        started = job.get('started_at')
        if started and now - started > JOB_TIMEOUT_SECONDS:
            job.update({
                'status': 'error',
                'error': 'タイムアウトしました(20分経過)',
                'bot_error': False,
                'completed_at': now,
            })
            _release_once(job)
            tmpdir = job.get('tmpdir')
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)


def _sweep_orphan_dirs(now):
    base = tempfile.gettempdir()
    try:
        names = os.listdir(base)
    except Exception as e:
        print(f'[cleanup] tmpディレクトリの一覧取得に失敗: {e}')
        names = []

    for name in names:
        if not name.startswith(TMP_PREFIX):
            continue
        path = os.path.join(base, name)
        if not os.path.isdir(path):
            continue
        job_id = name[len(TMP_PREFIX):]
        if job_id not in jobs:
            # jobs辞書に存在しない孤立ディレクトリ（tmpdir作成前に例外等が起きた場合など）
            shutil.rmtree(path, ignore_errors=True)

    # jobs辞書自体の掃除はディレクトリの有無に依存させない。
    # errorジョブはexcept節でtmpdirを即削除するため、ディレクトリ基準だと
    # 二度とここに引っかからずjobsに残り続けてしまう(メモリリーク)。
    # completed_at(done/error共通で付与)からの経過時間だけで判定する。
    with jobs_lock:
        stale_ids = [
            job_id for job_id, job in jobs.items()
            if job.get('status') in ('done', 'error')
            and job.get('completed_at')
            and now - job['completed_at'] > STALE_DIR_MAX_AGE_SECONDS
        ]
        removed = [jobs.pop(job_id) for job_id in stale_ids]

    # rmtreeのIO待ちでlockを長く握らないよう、pop後にlockの外で削除する
    for job in removed:
        tmpdir = job.get('tmpdir')
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def _maintenance_loop():
    last_sweep = time.time()  # 起動直後に全体掃除を走らせない
    while True:
        time.sleep(TIMEOUT_CHECK_INTERVAL_SECONDS)
        now = time.time()
        try:
            _check_job_timeouts(now)
            if now - last_sweep >= SWEEP_INTERVAL_SECONDS:
                _sweep_orphan_dirs(now)
                last_sweep = now
        except Exception as e:
            print(f'[maintenance] エラー: {e}')


threading.Thread(target=_maintenance_loop, daemon=True).start()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
