#!/usr/bin/env python3
"""
bootstrap.py — LessonRecorder First-Run Setup
==============================================
Запускается один раз при первом старте (или через меню «Настройки»).
Устанавливает все зависимости для текущей платформы.

Использование:
    python bootstrap.py              — интерактивный режим
    python bootstrap.py --silent     — тихий режим (для CI/installer)
    python bootstrap.py --check      — только проверка, без установки
"""

import sys
import os
import subprocess
import platform
import shutil
import argparse
from pathlib import Path

MIN_PYTHON = (3, 10)
REQUIRED_VERSION = "3.12"  # Рекомендуемая версия для установки

# ── Базовые пакеты (все платформы) ────────────────────────────────────────
BASE_PACKAGES = [
    "PyQt6>=6.5.0",
    "openai-whisper>=20231117",
    "faster-whisper>=1.0.0",
    "sounddevice>=0.4.6",
    "numpy>=1.24.0",
    "scipy>=1.11.0",
    "openai>=1.0.0",
    "requests>=2.31.0",
    "packaging>=23.0",
]

# ── Пакеты только для Windows ─────────────────────────────────────────────
WINDOWS_PACKAGES = [
    "PyAudioWPatch>=0.2.12",   # WASAPI loopback (запись системного звука)
]

# ── Опциональные пакеты (OCR и AI) ────────────────────────────────────────
OPTIONAL_PACKAGES = [
    "pytesseract>=0.3.10",
    "Pillow>=10.0.0",
    "opencv-python>=4.8.0",
    "google-generativeai>=0.3.0",
]


# ──────────────────────────────────────────────────────────────────────────
#  Утилиты
# ──────────────────────────────────────────────────────────────────────────

def log(msg: str, color: str = ""):
    """Цветной вывод в терминал."""
    RESET = "\033[0m"
    colors = {"green": "\033[92m", "red": "\033[91m",
              "yellow": "\033[93m", "blue": "\033[94m", "bold": "\033[1m"}
    prefix = colors.get(color, "")
    print(f"{prefix}{msg}{RESET if color else ''}")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Запускает команду, скрывая окно на Windows."""
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return subprocess.run(cmd, creationflags=flags, **kwargs)


def pip_install(packages: list[str], label: str = "") -> bool:
    """Устанавливает список пакетов через pip."""
    if not packages:
        return True
    if label:
        log(f"\n📦 Устанавливаю {label}...", "blue")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade",
           "--quiet", "--disable-pip-version-check"] + packages
    r = run(cmd, capture_output=False)
    return r.returncode == 0


def is_installed(import_name: str) -> bool:
    """Проверяет установку пакета."""
    try:
        r = run(
            [sys.executable, "-m", "pip", "show", import_name],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────
#  Проверка версии Python
# ──────────────────────────────────────────────────────────────────────────

def check_python_version() -> bool:
    ver = sys.version_info
    if ver < MIN_PYTHON:
        log(f"❌ Python {ver.major}.{ver.minor} слишком старый. "
            f"Нужен {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+", "red")
        return False
    log(f"✅ Python {ver.major}.{ver.minor}.{ver.micro}", "green")
    return True


# ──────────────────────────────────────────────────────────────────────────
#  Установка Python (если вызывают из скрипта установщика)
# ──────────────────────────────────────────────────────────────────────────

def install_python_windows():
    """Скачивает и устанавливает Python на Windows."""
    import urllib.request
    import tempfile

    url = f"https://www.python.org/ftp/python/{REQUIRED_VERSION}.0/python-{REQUIRED_VERSION}.0-amd64.exe"
    log(f"\n⬇️  Скачиваю Python {REQUIRED_VERSION}...", "blue")

    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
        tmp = f.name

    try:
        urllib.request.urlretrieve(url, tmp)
        log("🔧 Устанавливаю Python...", "blue")
        args = [tmp, "/quiet", "InstallAllUsers=0", "PrependPath=1",
                "Include_pip=1", "Include_launcher=0",
                "Include_test=0", "SimpleInstall=1"]
        r = subprocess.run(args, timeout=300)
        return r.returncode in (0, 3010)
    finally:
        Path(tmp).unlink(missing_ok=True)


def install_python_macos():
    """Устанавливает Python через Homebrew (macOS). Ставит сам Homebrew, если его нет."""
    brew = shutil.which("brew")
    if not brew:
        log("⚠️  Homebrew не найден — устанавливаю автоматически...", "yellow")
        try:
            install_cmd = (
                'NONINTERACTIVE=1 /bin/bash -c '
                '"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
            )
            r = subprocess.run(install_cmd, shell=True)
            if r.returncode != 0:
                raise RuntimeError(f"Homebrew installer exited {r.returncode}")
        except Exception as e:
            log(f"❌ Не удалось установить Homebrew автоматически: {e}", "red")
            log("   Установи Python вручную: https://www.python.org/downloads/macos/")
            log("   Или установи Homebrew: https://brew.sh  и затем: brew install python3")
            return False

        # Homebrew ставится в /opt/homebrew (Apple Silicon) или /usr/local (Intel)
        for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
            if Path(candidate).exists():
                brew = candidate
                break
        if not brew:
            log("❌ Homebrew установлен, но не найден по стандартному пути.", "red")
            return False
        log("✅ Homebrew установлен", "green")

    log(f"\n🍺 Устанавливаю Python {REQUIRED_VERSION} через Homebrew...", "blue")
    r = subprocess.run([brew, "install", f"python@{REQUIRED_VERSION}"])
    return r.returncode == 0


def install_python_linux():
    """Пытается установить Python через системный менеджер пакетов."""
    log("\n🐧 Определяю менеджер пакетов...", "blue")

    pkg_managers = [
        (shutil.which("apt-get"), ["sudo", "apt-get", "install", "-y",
                                   f"python{REQUIRED_VERSION}",
                                   f"python{REQUIRED_VERSION}-venv",
                                   "python3-pip"]),
        (shutil.which("dnf"),     ["sudo", "dnf", "install", "-y",
                                   f"python{REQUIRED_VERSION}"]),
        (shutil.which("pacman"),  ["sudo", "pacman", "-S", "--noconfirm", "python"]),
        (shutil.which("zypper"),  ["sudo", "zypper", "install", "-y", "python3"]),
    ]

    for mgr, cmd in pkg_managers:
        if mgr:
            log(f"  Используем: {Path(mgr).name}", "blue")
            r = subprocess.run(cmd)
            return r.returncode == 0

    log("⚠️  Автоустановка Python не удалась.", "yellow")
    log("   Установи Python 3.10+ вручную для своего дистрибутива.")
    return False


# ──────────────────────────────────────────────────────────────────────────
#  Основная логика
# ──────────────────────────────────────────────────────────────────────────

def setup(silent: bool = False, optional: bool = True):
    """Полная установка зависимостей."""
    log("\n" + "═" * 52, "bold")
    log("  LessonRecorder — Установка зависимостей", "bold")
    log("═" * 52, "bold")
    log(f"  Платформа: {platform.system()} {platform.machine()}")
    log(f"  Python:    {sys.version.split()[0]}")
    log("═" * 52)

    if not check_python_version():
        sys.exit(1)

    # Обновляем pip
    log("\n⬆️  Обновляю pip...", "blue")
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pip",
         "--quiet"], capture_output=True)

    # Базовые пакеты
    ok = pip_install(BASE_PACKAGES, "базовые компоненты")
    if not ok:
        log("❌ Не удалось установить базовые пакеты.", "red")
        if not silent:
            sys.exit(1)

    # Windows-specific
    if sys.platform == "win32":
        pip_install(WINDOWS_PACKAGES, "Windows Audio (WASAPI)")

    # Опциональные
    if optional:
        pip_install(OPTIONAL_PACKAGES, "опциональные компоненты (OCR, Gemini)")

    # Проверка результата
    log("\n" + "─" * 52)
    log("  Проверка установки:", "bold")
    checks = [
        ("PyQt6",          "PyQt6"),
        ("faster-whisper", "faster_whisper"),
        ("sounddevice",    "sounddevice"),
        ("openai",         "openai"),
        ("requests",       "requests"),
    ]
    all_ok = True
    for pip_name, import_name in checks:
        ok = is_installed(pip_name)
        icon = "✅" if ok else "❌"
        color = "green" if ok else "red"
        log(f"  {icon} {pip_name}", color)
        if not ok:
            all_ok = False

    log("─" * 52)
    if all_ok:
        log("\n✅ Все компоненты установлены. Можно запускать LessonRecorder!\n",
            "green")
    else:
        log("\n⚠️  Некоторые компоненты не установились.", "yellow")
        log("   Попробуй: pip install -r requirements.txt\n")

    return all_ok


def check_only():
    """Только проверка без установки."""
    log("\n📋 Проверка зависимостей LessonRecorder")
    log("─" * 40)
    all_ok = True
    for pip_name, *_ in [(p.split(">=")[0], ) for p in BASE_PACKAGES]:
        ok = is_installed(pip_name)
        icon = "✅" if ok else "❌"
        color = "green" if ok else "red"
        log(f"  {icon} {pip_name}", color)
        if not ok:
            all_ok = False
    if all_ok:
        log("\n✅ Все зависимости в порядке.\n", "green")
    else:
        log("\n❌ Есть отсутствующие пакеты. Запусти: python bootstrap.py\n", "red")
    return all_ok


# ──────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LessonRecorder — установка зависимостей")
    parser.add_argument("--silent",   action="store_true",
                        help="тихий режим (без остановок)")
    parser.add_argument("--check",    action="store_true",
                        help="только проверка, без установки")
    parser.add_argument("--no-optional", action="store_true",
                        help="пропустить опциональные пакеты (OCR, Gemini)")
    args = parser.parse_args()

    if args.check:
        ok = check_only()
        sys.exit(0 if ok else 1)
    else:
        ok = setup(silent=args.silent, optional=not args.no_optional)
        sys.exit(0 if ok else 1)
