# LessonRecorder.spec — кросс-платформенная сборка
# Работает на Windows, macOS и Linux.
# Использование: pyinstaller LessonRecorder.spec --clean --noconfirm

import sys
import os
from pathlib import Path

# ── Константы ─────────────────────────────────────────────────────────────
APP_NAME   = "LessonRecorder"
ENTRY      = "main.py"
BASE_DIR   = Path(SPEC).parent       # Корень проекта (рядом со .spec)

IS_WIN     = sys.platform == "win32"
IS_MAC     = sys.platform == "darwin"
IS_LINUX   = sys.platform.startswith("linux")

# ── Иконка (платформо-зависимая) ──────────────────────────────────────────
def _icon():
    if IS_WIN:
        p = BASE_DIR / "app_icon.ico"
    elif IS_MAC:
        p = BASE_DIR / "app_icon.icns"
        if not p.exists():
            p = BASE_DIR / "app_icon.png"
    else:
        p = BASE_DIR / "app_icon.png"
    return str(p) if p.exists() else None

ICON = _icon()

# ── Дополнительные данные (скопировать рядом с бинарником) ────────────────
datas = []

# Иконки
for name in ["app_icon.ico", "app_icon.icns", "app_icon.png"]:
    p = BASE_DIR / name
    if p.exists():
        datas.append((str(p), "."))

# Прочие ресурсы (если есть)
for resource_dir in ["assets", "resources", "locale"]:
    p = BASE_DIR / resource_dir
    if p.exists():
        datas.append((str(p), resource_dir))

# ── Скрытые импорты (нужны для faster-whisper / ctranslate2) ──────────────
hiddenimports = [
    "faster_whisper",
    "ctranslate2",
    "whisper",
    "sounddevice",
    "soundfile",
    "scipy.signal",
    "scipy.io.wavfile",
    "numpy",
    "openai",
    "requests",
    "packaging",
    "google.generativeai",
    # PyQt6 плагины
    "PyQt6.QtWidgets",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtMultimedia",
    "PyQt6.sip",
]

if IS_WIN:
    hiddenimports += ["pyaudiowpatch", "win32api", "win32con"]
if IS_MAC:
    hiddenimports += ["AppKit", "Foundation"]

# ── Исключения (уменьшаем размер бандла) ──────────────────────────────────
excludes = [
    "matplotlib", "tkinter", "unittest", "test",
    "IPython", "jupyter", "notebook",
    "pandas", "sklearn", "torch",    # Torch тяжёлый — whisper без него тоже работает
    "torchvision", "torchaudio",
]

# ─────────────────────────────────────────────────────────────────────────

a = Analysis(
    [str(BASE_DIR / ENTRY)],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,      # Без терминального окна
    disable_windowed_traceback=False,
    argv_emulation=IS_MAC,   # macOS: передача файлов через Finder
    target_arch=None,        # None = текущая арх. (arm64 или x86_64)
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
    version="version_info.txt" if IS_WIN else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

# ── macOS: .app bundle ────────────────────────────────────────────────────
if IS_MAC:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON,
        bundle_identifier="com.render.lessonrecorder",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSMicrophoneUsageDescription":
                "LessonRecorder использует микрофон для записи уроков.",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.15",
            "NSRequiresAquaSystemAppearance": False,  # поддержка Dark Mode
        },
    )
