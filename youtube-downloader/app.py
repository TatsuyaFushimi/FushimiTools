import os
import tempfile
import uuid
import threading
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
jobs = {}


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

        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
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
        return jsonify({'error': str(e)}), 400


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
        fmt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best'
    else:
        fmt = (
            f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/'
            f'bestvideo[height<={height}]+bestaudio/'
            f'best[height<={height}][ext=mp4]/'
            f'best[height<={height}]'
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
        'format': fmt,
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
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
        jobs[job_id].update({'status': 'error', 'error': str(e)})


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
    return send_file(job['filepath'], as_attachment=True, download_name=job['filename'])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    is_local = port == 5000
    if is_local:
        print('起動中... ブラウザで http://localhost:5000 を開いてください')
    app.run(debug=False, host='0.0.0.0', port=port)
