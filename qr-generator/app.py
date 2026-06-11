import os
import io
import base64
import secrets
import string
from flask import Flask, render_template, request, jsonify, redirect
import qrcode
import bcrypt
from supabase import create_client

app = Flask(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
APP_URL = os.environ.get('APP_URL', 'http://localhost:5000').rstrip('/')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None


def _gen_id(length=6):
    chars = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def _make_qr_b64(url: str) -> str:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/r/<qr_id>')
def redirect_qr(qr_id):
    if not supabase:
        return 'サーバー設定エラー', 500
    result = supabase.table('qr_codes').select('destination_url').eq('id', qr_id).single().execute()
    if result.data:
        return redirect(result.data['destination_url'])
    return 'QRコードが見つかりません', 404


@app.route('/api/create', methods=['POST'])
def create_qr():
    if not supabase:
        return jsonify({'error': 'サーバー設定エラー'}), 500

    data = request.json or {}
    title = data.get('title', '').strip()
    url = data.get('url', '').strip()
    password = data.get('password', '').strip()
    creator = data.get('creator', '').strip()

    if not title:
        return jsonify({'error': 'タイトルを入力してください'}), 400
    if not url:
        return jsonify({'error': 'URLを入力してください'}), 400
    if not password:
        return jsonify({'error': 'パスワードを設定してください'}), 400
    if not creator:
        return jsonify({'error': '作成者名を入力してください'}), 400
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'URLは http:// または https:// で始めてください'}), 400

    for _ in range(10):
        qr_id = _gen_id()
        existing = supabase.table('qr_codes').select('id').eq('id', qr_id).execute()
        if not existing.data:
            break

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    supabase.table('qr_codes').insert({
        'id': qr_id,
        'title': title,
        'destination_url': url,
        'password_hash': pw_hash,
        'creator': creator,
    }).execute()

    redirect_url = f'{APP_URL}/r/{qr_id}'
    return jsonify({
        'id': qr_id,
        'redirect_url': redirect_url,
        'qr_image': _make_qr_b64(redirect_url),
    })


@app.route('/api/search')
def search_qr():
    q = request.args.get('q', '').strip().lower()
    if not q:
        return jsonify({'results': []})
    if not supabase:
        return jsonify({'error': 'サーバー設定エラー'}), 500

    try:
        rows = supabase.table('qr_codes').select('id,title,creator,destination_url').execute()
        results = [
            {'id': r['id'], 'title': r['title'], 'creator': r['creator'], 'url': r['destination_url']}
            for r in rows.data
            if q in r.get('title', '').lower() or q in r.get('creator', '').lower()
        ]
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/edit', methods=['POST'])
def edit_qr():
    if not supabase:
        return jsonify({'error': 'サーバー設定エラー'}), 500

    data = request.json or {}
    qr_id = data.get('id', '').strip()
    password = data.get('password', '').strip()
    new_url = data.get('new_url', '').strip()

    if not qr_id or not password or not new_url:
        return jsonify({'error': '全項目を入力してください'}), 400
    if not new_url.startswith(('http://', 'https://')):
        return jsonify({'error': 'URLは http:// または https:// で始めてください'}), 400

    result = supabase.table('qr_codes').select('password_hash').eq('id', qr_id).single().execute()
    if not result.data:
        return jsonify({'error': 'QRコードが見つかりません'}), 404

    if not bcrypt.checkpw(password.encode(), result.data['password_hash'].encode()):
        return jsonify({'error': 'パスワードが違います'}), 403

    supabase.table('qr_codes').update({'destination_url': new_url}).eq('id', qr_id).execute()
    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    if port == 5000:
        print('起動中... ブラウザで http://localhost:5000 を開いてください')
    app.run(debug=False, host='0.0.0.0', port=port)
