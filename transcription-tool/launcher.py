import sys
import os
import subprocess
import threading
import time

if getattr(sys, 'frozen', False):
    # macOS .app: datas land in Contents/Resources, not _MEIPASS (Contents/Frameworks)
    _resources = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), 'Resources')
    BASE_DIR = _resources if os.path.isdir(os.path.join(_resources, 'templates')) else sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

import app as transcript_app

transcript_app.app.template_folder = os.path.join(BASE_DIR, 'templates')
transcript_app.app.static_folder = os.path.join(BASE_DIR, 'static')


PORT = 5002


def _kill_existing(port):
    import subprocess
    try:
        result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
        for pid in result.stdout.strip().split('\n'):
            if pid.strip():
                subprocess.run(['kill', '-9', pid.strip()], capture_output=True)
        time.sleep(0.5)
    except Exception:
        pass


def _finish_launching():
    """macOSにアプリ起動完了を通知してDockの跳ねを止める"""
    try:
        import ctypes, ctypes.util
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cls = objc.objc_getClass(b'NSApplication')
        app = objc.objc_msgSend(cls, objc.sel_registerName(b'sharedApplication'))
        objc.objc_msgSend(app, objc.sel_registerName(b'finishLaunching'))
    except Exception:
        pass


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
    _finish_launching()
    _kill_existing(PORT)
    threading.Thread(target=_open_browser, args=(PORT,), daemon=True).start()
    transcript_app.app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)
