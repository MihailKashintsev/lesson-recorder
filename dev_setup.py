#!/usr/bin/env python3
"""
dev_setup.py — Настройка среды разработки LessonRecorder
=========================================================
Работает на Windows, macOS и Linux.

Выполняет:
  1. Проверяет версию Python
  2. Создаёт виртуальное окружение (venv)
  3. Устанавливает все зависимости
  4. Устанавливает платформо-специфичные пакеты
  5. Выводит инструкции по запуску

Использование:
    python dev_setup.py           # полная настройка
    python dev_setup.py --reset   # пересоздать venv
"""

import sys
import os
import subprocess
import shutil
import platform
from pathlib import Path

BASE_DIR = Path(__file__).parent
VENV_DIR = BASE_DIR / ".venv"

IS_WIN   = sys.platform == "win32"
IS_MAC   = sys.platform == "darwin"
IS_LINUX = not IS_WIN and not IS_MAC

# Путь к python/pip внутри venv
if IS_WIN:
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
    VENV_PIP    = VENV_DIR / "Scripts" / "pip.exe"
    ACTIVATE    = str(VENV_DIR / "Scripts" / "activate.bat")
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python3"
    VENV_PIP    = VENV_DIR / "bin" / "pip3"
    ACTIVATE    = f"source {VENV_DIR}/bin/activate"


# ── Цвета ─────────────────────────────────────────────────────────────────
def c(text, code):
    if IS_WIN:
        try:
            import colorama; colorama.init()
        except ImportError:
            return text
    return f"\033[{code}m{text}\033[0m"

ok   = lambda t: print(c(f"✅  {t}", "92"))
err  = lambda t: print(c(f"❌  {t}", "91"))
info = lambda t: print(c(f"ℹ️   {t}", "94"))
warn = lambda t: print(c(f"⚠️   {t}", "93"))
step = lambda t: print(c(f"\n── {t} ──", "1"))


def run(cmd, **kw):
    flags = 0
    if IS_WIN:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(cmd, creationflags=flags, **kw)


# ─────────────────────────────────────────────────────────────────────────

def check_python():
    step("Проверка Python")
    v = sys.version_info
    print(f"  Python {v.major}.{v.minor}.{v.micro} ({platform.machine()})")
    if v < (3, 10):
        err(f"Нужен Python 3.10+, установлен {v.major}.{v.minor}")

        if IS_MAC:
            print("\n  Установи Python:")
            print("    brew install python3")
            print("    или скачай с https://www.python.org/downloads/macos/")
        elif IS_WIN:
            print("\n  Скачай Python с https://www.python.org/downloads/windows/")
            print("  (включи 'Add Python to PATH')")
        else:
            print("\n  sudo apt install python3.12  (Ubuntu/Debian)")
            print("  sudo dnf install python3.12  (Fedora)")

        sys.exit(1)
    ok(f"Python {v.major}.{v.minor}.{v.micro}")


def create_venv(reset: bool = False):
    step("Виртуальное окружение")
    if reset and VENV_DIR.exists():
        warn("Удаляю старое venv...")
        shutil.rmtree(VENV_DIR)

    if not VENV_DIR.exists():
        info("Создаю .venv...")
        r = run([sys.executable, "-m", "venv", str(VENV_DIR)])
        if r.returncode != 0:
            err("Не удалось создать venv")
            sys.exit(1)
        ok("venv создан")
    else:
        ok("venv уже существует")


def upgrade_pip():
    step("Обновление pip")
    r = run(
        [str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip",
         "--quiet"],
        capture_output=True,
    )
    ok("pip обновлён") if r.returncode == 0 else warn("pip не обновился")


def install_deps():
    step("Установка зависимостей")
    req = BASE_DIR / "requirements.txt"
    if not req.exists():
        err("requirements.txt не найден!")
        sys.exit(1)

    info("Устанавливаю requirements.txt...")
    r = run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(req),
             "--quiet", "--disable-pip-version-check"])
    if r.returncode != 0:
        err("Ошибка установки зависимостей")
        sys.exit(1)
    ok("Зависимости установлены")

    # PyInstaller для сборки
    run([str(VENV_PYTHON), "-m", "pip", "install", "pyinstaller",
         "--quiet", "--disable-pip-version-check"], capture_output=True)
    ok("PyInstaller установлен")

    # Windows-only
    if IS_WIN:
        info("Windows: устанавливаю PyAudioWPatch...")
        r = run([str(VENV_PYTHON), "-m", "pip", "install", "PyAudioWPatch",
                 "--quiet"])
        ok("PyAudioWPatch") if r.returncode == 0 else warn("PyAudioWPatch не установился")

    # macOS: portaudio через brew
    if IS_MAC:
        if shutil.which("brew"):
            info("macOS: устанавливаю portaudio через Homebrew...")
            run(["brew", "install", "portaudio"], capture_output=True)
            ok("portaudio")
        else:
            warn("Homebrew не найден. Установи с https://brew.sh")

    # Linux: проверяем portaudio
    if IS_LINUX:
        if not shutil.which("portaudio"):
            warn("portaudio не найден.")
            warn("Ubuntu/Debian: sudo apt install libportaudio2 portaudio19-dev")
            warn("Fedora: sudo dnf install portaudio-devel")


def print_summary():
    step("Готово")
    print()
    ok("Окружение настроено!")
    print()
    print(c("  Для запуска проекта:", "1"))
    if IS_WIN:
        print(f"    {ACTIVATE}")
    else:
        print(f"    {ACTIVATE}")
    print(f"    python main.py")
    print()
    print(c("  Для сборки:", "1"))
    if IS_WIN:
        print("    build.bat")
    else:
        print("    chmod +x build.sh && ./build.sh")
    print()
    print(c("  Полезные команды:", "1"))
    print(f"    {VENV_PYTHON} bootstrap.py --check   # проверка зависимостей")
    print(f"    {VENV_PIP} list                       # список пакетов")
    print()


# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    reset = "--reset" in sys.argv

    print(c("\n  LessonRecorder — Dev Setup", "1;94"))
    print(c(f"  Платформа: {platform.system()} {platform.machine()}", "94"))
    print()

    check_python()
    create_venv(reset)
    upgrade_pip()
    install_deps()
    print_summary()
