import os
import io
import json
import base64
import secrets
import string
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, redirect
import qrcode
import bcrypt
from supabase import create_client

app = Flask(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
APP_URL = os.environ.get('APP_URL', 'http://localhost:5000').rstrip('/')
GSHEET_CREDS_B64 = os.environ.get('GSHEET_CREDS_B64', '')
GSHEET_ID = os.environ.get('GSHEET_ID', '')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None


def _log_to_sheet(channel_name: str, title: str, url: str, password: str, creator: str, qr_id: str):
    if not GSHEET_CREDS_B64 or not GSHEET_ID:
        return
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds_json = json.loads(base64.b64decode(GSHEET_CREDS_B64).decode())
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GSHEET_ID)
        ws = sh.sheet1
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        ws.append_row([channel_name, now, title, url, password, creator, qr_id])
    except Exception:
        pass  # サイレント失敗


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


@app.route('/api/qr/<qr_id>')
def get_qr(qr_id):
    if not supabase:
        return jsonify({'error': 'サーバー設定エラー'}), 500
    result = supabase.table('qr_codes').select('title').eq('id', qr_id).single().execute()
    if not result.data:
        return jsonify({'error': 'QRコードが見つかりません'}), 404
    redirect_url = f'{APP_URL}/r/{qr_id}'
    return jsonify({
        'qr_image': _make_qr_b64(redirect_url),
        'title': result.data['title'],
    })


@app.route('/api/create', methods=['POST'])
def create_qr():
    if not supabase:
        return jsonify({'error': 'サーバー設定エラー'}), 500

    data = request.json or {}
    channel_name = data.get('channel_name', '').strip()
    title = data.get('title', '').strip()
    url = data.get('url', '').strip()
    password = data.get('password', '').strip()
    creator = data.get('creator', '').strip()

    if not channel_name:
        return jsonify({'error': 'ch名を選択してください'}), 400
    if not title:
        return jsonify({'error': 'タイトルを入力してください'}), 400
    if not url:
        url = 'https://www.busoken.com/'
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
        'channel_name': channel_name,
        'title': title,
        'destination_url': url,
        'password_hash': pw_hash,
        'creator': creator,
    }).execute()

    _log_to_sheet(channel_name, title, url, password, creator, qr_id)

    redirect_url = f'{APP_URL}/r/{qr_id}'
    return jsonify({
        'id': qr_id,
        'title': title,
        'redirect_url': redirect_url,
        'qr_image': _make_qr_b64(redirect_url),
    })


@app.route('/api/list')
def list_qr():
    if not supabase:
        return jsonify({'error': 'サーバー設定エラー'}), 500
    try:
        rows = supabase.table('qr_codes').select(
            'id,channel_name,title,creator,destination_url,created_at'
        ).order('created_at', desc=True).execute()
        return jsonify({'items': rows.data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scan-counts')
def scan_counts():
    if not supabase:
        return jsonify({}), 200
    try:
        result = supabase.table('qr_scans').select('qr_id').execute()
        counts = {}
        for row in result.data:
            qr_id = row['qr_id']
            counts[qr_id] = counts.get(qr_id, 0) + 1
        return jsonify(counts)
    except Exception:
        return jsonify({}), 200


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
