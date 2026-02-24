# -*- mode: python ; coding: utf-8 -*-
"""
LessonRecorder.spec

ВАЖНО: transcribe_worker.py включается как DATA-файл (.py), а не как модуль.
Это нужно чтобы запускать его через пользовательский python.exe в рантайме,
а не через bundled Python который не видит AppData-пакеты.
"""

from pathlib import Path

block_cipher = None

# Дополнительные данные: воркер .py и папки ресурсов
added_files = [
    # Воркер транскрипции — .py файл, запускается отдельным python.exe
    ("core/transcribe_worker.py", "core"),
]

# Иконка — добавляем в bundle чтобы main.py нашёл её через sys._MEIPASS
if Path("app_icon.ico").exists():
    added_files.append(("app_icon.ico", "."))

# Добавляем ресурсы если есть
for extra in ["resources", "assets", "tessdata"]:
    if Path(extra).exists():
        added_files.append((extra, extra))

# Иконка для EXE файла
icon_path = "app_icon.ico" if Path("app_icon.ico").exists() else None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "core.transcribe_worker",
        "core.python_path",
        "PyQt6.QtCore",
        "PyQt6.QtWidgets",
        "PyQt6.QtGui",
        "sounddevice",
        "numpy",
        "scipy",
        "scipy.signal",
        "requests",
        "packaging",
        "packaging.version",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # НЕ включаем whisper и faster_whisper в бандл —
        # они устанавливаются пользователем в свой Python
        "faster_whisper",
        "whisper",
        "torch",
        "ctranslate2",
    ],
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
    console=False,           # GUI приложение — без консоли
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
    version="version_info.txt" if Path("version_info.txt").exists() else None,
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
