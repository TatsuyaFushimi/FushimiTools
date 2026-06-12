import os
import shutil
import subprocess
import tempfile
import uuid
import threading
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

jobs = {}
MODELS_DIR = os.path.expanduser('~/.flare-transcript/models')
os.makedirs(MODELS_DIR, exist_ok=True)


def _ffmpeg_path():
    for path in ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg']:
        if os.path.exists(path):
            return path
    return shutil.which('ffmpeg')


def _seconds_to_srt(s):
    h, r = divmod(int(s), 3600)
    m, sec = divmod(r, 60)
    ms = int((s % 1) * 1000)
    return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'


def _extract_audio_yt(url, tmpdir):
    import yt_dlp
    ffmpeg = _ffmpeg_path()
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(tmpdir, 'audio.%(ext)s'),
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
        'quiet': True,
        'no_warnings': True,
    }
    if ffmpeg:
        opts['ffmpeg_location'] = os.path.dirname(ffmpeg)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    title = info.get('title', 'transcript')
    return os.path.join(tmpdir, 'audio.mp3'), title


def _extract_audio_file(video_path, tmpdir):
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError('ffmpegが見つかりません。Homebrewでインストールしてください: brew install ffmpeg')
    audio_path = os.path.join(tmpdir, 'audio.mp3')
    subprocess.run(
        [ffmpeg, '-i', video_path, '-vn', '-acodec', 'mp3', '-q:a', '2', audio_path, '-y'],
        capture_output=True, check=True
    )
    return audio_path


def _do_transcribe(job_id, audio_path, title, language, model_size):
    try:
        from faster_whisper import WhisperModel

        jobs[job_id].update({'status': 'loading_model', 'progress': 0})
        model = WhisperModel(model_size, device='cpu', compute_type='int8', download_root=MODELS_DIR)

        jobs[job_id].update({'status': 'transcribing', 'progress': 0})
        lang = None if language == 'auto' else language
        segments, info = model.transcribe(audio_path, beam_size=5, language=lang, vad_filter=True)
        duration = info.duration or 1

        txt_parts, srt_parts = [], []
        idx = 1
        for seg in segments:
            text = seg.text.strip()
            if text:
                txt_parts.append(text)
                s = _seconds_to_srt(seg.start)
                e = _seconds_to_srt(seg.end)
                srt_parts.append(f'{idx}\n{s} --> {e}\n{text}\n')
                idx += 1
            jobs[job_id]['progress'] = min(99, int(seg.end / duration * 100))

        txt = '\n'.join(txt_parts)
        srt = '\n'.join(srt_parts)
        jobs[job_id].update({
            'status': 'done',
            'progress': 100,
            'title': title,
            'txt': txt,
            'srt': srt,
            'preview': txt[:500],
        })
    except Exception as e:
        jobs[job_id].update({'status': 'error', 'error': str(e)})


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/transcribe-url', methods=['POST'])
def transcribe_url():
    data = request.json or {}
    url = data.get('url', '').strip()
    language = data.get('language', 'ja')
    model_size = data.get('model', 'small')
    if not url:
        return jsonify({'error': 'URLを入力してください'}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'downloading', 'progress': 0}

    def run():
        tmpdir = tempfile.mkdtemp()
        try:
            audio_path, title = _extract_audio_yt(url, tmpdir)
            _do_transcribe(job_id, audio_path, title, language, model_size)
        except Exception as e:
            jobs[job_id].update({'status': 'error', 'error': str(e)})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'job_id': job_id})


@app.route('/api/transcribe-file', methods=['POST'])
def transcribe_file():
    if 'file' not in request.files:
        return jsonify({'error': 'ファイルがありません'}), 400
    f = request.files['file']
    language = request.form.get('language', 'ja')
    model_size = request.form.get('model', 'small')
    title = os.path.splitext(f.filename or 'transcript')[0]

    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'extracting', 'progress': 0}

    tmpdir = tempfile.mkdtemp()
    video_path = os.path.join(tmpdir, 'video.mp4')
    f.save(video_path)

    def run():
        try:
            audio_path = _extract_audio_file(video_path, tmpdir)
            _do_transcribe(job_id, audio_path, title, language, model_size)
        except Exception as e:
            jobs[job_id].update({'status': 'error', 'error': str(e)})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'job_id': job_id})


@app.route('/api/progress/<job_id>')
def get_progress(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'ジョブが見つかりません'}), 404
    return jsonify(job)


@app.route('/api/download/<job_id>/<fmt>')
def download(job_id, fmt):
    job = jobs.get(job_id)
    if not job or job.get('status') != 'done':
        return 'ファイルの準備ができていません', 404
    if fmt not in ('txt', 'srt'):
        return 'フォーマットエラー', 400
    content = job[fmt]
    safe_name = (job.get('title') or 'transcript').replace('/', '_')[:80]
    resp = Response(content, mimetype='text/plain; charset=utf-8')
    resp.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{safe_name}.{fmt}"
    return resp


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(debug=False, host='127.0.0.1', port=port)
