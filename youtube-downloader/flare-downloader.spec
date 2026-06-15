# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static',    'static'),
    ],
    hiddenimports=[
        'flask',
        'flask.templating',
        'jinja2',
        'jinja2.ext',
        'werkzeug',
        'werkzeug.routing',
        'werkzeug.serving',
        'yt_dlp',
        'yt_dlp.extractor.lazy_extractors',
        'yt_dlp.downloader',
        'yt_dlp.postprocessor',
        'yt_dlp.utils',
        'yt_dlp.networking',
        'yt_dlp.networking.common',
        'yt_dlp.networking._urllib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FlareDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FlareDownloader',
)

app = BUNDLE(
    coll,
    name='Flare Downloader.app',
    icon='FlareDownloader.icns',
    bundle_identifier='com.fushimitools.flaredownloader',
    info_plist={
        'CFBundleName': 'Flare Downloader',
        'CFBundleDisplayName': 'Flare Downloader',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'LSUIElement': True,
    },
)
