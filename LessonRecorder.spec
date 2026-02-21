# -*- mode: python ; coding: utf-8 -*-
# LessonRecorder.spec
# PyInstaller сборочный файл — запускать через:
#   pyinstaller LessonRecorder.spec

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
import sys

block_cipher = None

# Собираем данные faster-whisper (модели токенизатора)
datas = []
datas += collect_data_files("faster_whisper")
datas += collect_data_files("av")  # PyAV для faster-whisper

# Собираем нативные библиотеки
binaries = []
binaries += collect_dynamic_libs("sounddevice")

a = Analysis(
    ["main.py", "core/transcribe_worker.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "PyQt6",
        "PyQt6.QtWidgets",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "faster_whisper",
        "sounddevice",
        "numpy",
        "scipy",
        "scipy.signal",
        "requests",
        "packaging",
        "packaging.version",
        "sqlite3",
        "wave",
        "ctranslate2",
        "tokenizers",
        "huggingface_hub",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PIL", "IPython"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LessonRecorder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # без консольного окна
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="installer/icon.ico",   # иконка (создай или удали строку)
    version="installer/version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LessonRecorder",
)
