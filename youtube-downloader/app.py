import os
import base64
import shutil
import tempfile
import uuid
import threading
from flask import Flask, render_template, request, jsonify, send_file, after_this_request

app = Flask(__name__)
jobs = {}

COOKIES_PATH = '/tmp/yt_cookies.txt'
_cookie_check_cache = {'valid': None, 'checked_at': 0}


def _init_cookies():
    """環境変数にCookieが設定されていれば起動時にファイルへ書き出す"""
    b64 = os.environ.get('YOUTUBE_COOKIES_B64', '')
    if b64:
        try:
            with open(COOKIES_PATH, 'wb') as f:
                f.write(base64.b64decode(b64))
            print('YouTube cookies loaded from environment variable')
        except Exception as e:
            print(f'Failed to load cookies from env: {e}')


_init_cookies()


def _ffmpeg_location():
    # PyInstallerバンドル環境ではPATHが通らないため明示的に探す
    for path in ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg']:
        if os.path.exists(path):
            return os.path.dirname(path)
    found = shutil.which('ffmpeg')
    return os.path.dirname(found) if found else None


def _ydl_opts_base():
    opts = {'quiet': True, 'no_warnings': True}
    if os.path.exists(COOKIES_PATH):
        opts['cookiefile'] = COOKIES_PATH
    loc = _ffmpeg_location()
    if loc:
        opts['ffmpeg_location'] = loc
    return opts


def _is_bot_error(msg: str) -> bool:
    return 'Sign in to confirm' in msg or 'bot' in msg.lower()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/info', methods=['POST'])
def get_info():
    try:
        import yt_dlp
        url = request.json.get('url', '').strip()
        if not url:
            return jsonify({'error': 'URLを入力してください'}), 400

        with yt_dlp.YoutubeDL(_ydl_opts_base()) as ydl:
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
    data = request.json
    url = data.get('url', '').strip()
    height = data.get('height')

    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'downloading', 'progress': 0, 'speed': '', 'eta': ''}

    t = threading.Thread(target=_do_download, args=(job_id, url, height), daemon=True)
    t.start()

    return jsonify({'job_id': job_id})


def _do_download(job_id, url, height):
    import yt_dlp

    tmpdir = tempfile.mkdtemp()

    if not height or height == 'best':
        fmt = 'bestvideo+bestaudio/best'
    else:
        fmt = (
            f'bestvideo[height<={height}]+bestaudio/'
            f'best[height<={height}]/'
            f'best'
        )

    def progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            jobs[job_id]['progress'] = round(downloaded / total * 100) if total else 0
            jobs[job_id]['speed'] = d.get('_speed_str', '').strip()
            jobs[job_id]['eta'] = d.get('_eta_str', '').strip()
        elif d['status'] == 'finished':
            jobs[job_id]['progress'] = 99
            jobs[job_id]['eta'] = 'マージ中...'

    opts = {
        **_ydl_opts_base(),
        'format': fmt,
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'progress_hooks': [progress_hook],
    }

    try:
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

        jobs[job_id].update({
            'status': 'done',
            'filepath': mp4_path,
            'filename': os.path.basename(mp4_path),
            'progress': 100,
            'eta': '',
        })

    except Exception as e:
        msg = str(e)
        jobs[job_id].update({
            'status': 'error',
            'error': msg,
            'bot_error': _is_bot_error(msg),
        })


@app.route('/api/progress/<job_id>')
def get_progress(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'ジョブが見つかりません'}), 404
    return jsonify(job)


@app.route('/api/file/<job_id>')
def serve_file(job_id):
    job = jobs.get(job_id)
    if not job or job.get('status') != 'done':
        return 'ファイルの準備ができていません', 404

    filepath = job['filepath']
    tmpdir = os.path.dirname(filepath)

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
            jobs.pop(job_id, None)
        except Exception:
            pass
        return response

    return send_file(filepath, as_attachment=True, download_name=job['filename'])


@app.route('/api/cookie-script')
def cookie_script():
    """Gatekeeper回避: ファイル保存せずcurl|bashで直接実行させる"""
    path = os.path.join(os.path.dirname(__file__), 'update-cookies.command')
    with open(path, 'r') as f:
        content = f.read()
    from flask import Response
    return Response(content, mimetype='text/plain')


@app.route('/api/cookies', methods=['POST'])
def upload_cookies():
    if 'file' not in request.files:
        return jsonify({'error': 'ファイルがありません'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'ファイルが空です'}), 400
    f.save(COOKIES_PATH)
    return jsonify({'ok': True})


@app.route('/api/cookies/status')
def cookies_status():
    return jsonify({'has_cookies': os.path.exists(COOKIES_PATH)})


@app.route('/api/cookies/check')
def cookies_check():
    import time, yt_dlp
    cache = _cookie_check_cache

    # 30分以内にチェック済みならキャッシュを返す（?refresh=1 で強制リフレッシュ）
    force = request.args.get('refresh') == '1'
    if not force and cache['valid'] is not None and time.time() - cache['checked_at'] < 1800:
        return jsonify({'status': 'valid' if cache['valid'] else 'expired'})

    if not os.path.exists(COOKIES_PATH):
        return jsonify({'status': 'none'})

    try:
        opts = {**_ydl_opts_base(), 'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            # 軽量テスト: 短い動画の情報だけ取得（ダウンロードなし）
            ydl.extract_info(
                'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                download=False,
                process=False,
            )
        cache['valid'] = True
        cache['checked_at'] = time.time()
        return jsonify({'status': 'valid'})
    except Exception as e:
        cache['valid'] = False
        cache['checked_at'] = time.time()
        status = 'expired' if _is_bot_error(str(e)) else 'error'
        return jsonify({'status': status})


@app.route('/api/status')
def status():
    total, used, free = shutil.disk_usage('/tmp')
    return jsonify({
        'disk_total_gb': round(total / 1e9, 2),
        'disk_used_gb': round(used / 1e9, 2),
        'disk_free_gb': round(free / 1e9, 2),
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    if port == 5000:
        print('起動中... ブラウザで http://localhost:5000 を開いてください')
    app.run(debug=False, host='0.0.0.0', port=port)
