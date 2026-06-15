import sys
import os
import subprocess
import threading
import time
import socket

# PyInstallerバンドル時のリソースパスを解決
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from flask import Flask, render_template, request, jsonify, send_file, after_this_request
import app as flare_app

# バンドル内のtemplates/staticを参照させる
flare_app.app.template_folder = os.path.join(BASE_DIR, 'templates')
flare_app.app.static_folder   = os.path.join(BASE_DIR, 'static')

PORT = 5001


def _find_free_port():
    for p in range(5001, 5020):
        try:
            s = socket.socket()
            s.bind(('127.0.0.1', p))
            s.close()
            return p
        except OSError:
            continue
    return 5001


def _open_browser(port):
    import urllib.request
    for _ in range(240):
        try:
            urllib.request.urlopen(f'http://localhost:{port}/', timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    subprocess.run(['open', f'http://localhost:{port}'])


if __name__ == '__main__':
    port = _find_free_port()
    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()
    flare_app.app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
