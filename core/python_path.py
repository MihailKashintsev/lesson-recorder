"""
Утилита для поиска реального интерпретатора Python.

В PyInstaller-бандле sys.executable = LessonRecorder(.exe/.app), а не python.
Запускать его с '-m pip' нельзя.

Порядок поиска (Windows):
  1. Рядом с exe  2. PATH  3. Реестр  4. Стандартные папки  5. py.exe лаунчер

Порядок поиска (macOS):
  1. Рядом с .app  2. PATH  3. Homebrew  4. pyenv  5. Стандартные /usr пути

Порядок поиска (Linux):
  1. Рядом с бинарником  2. PATH  3. pyenv  4. /usr/bin  5. Системные менеджеры
"""
import sys
import os
import shutil
import subprocess
from pathlib import Path


# ── Утилиты ──────────────────────────────────────────────────────────────────

def _is_valid_python(path: str | Path, min_ver: tuple = (3, 10)) -> bool:
    """Проверяет что путь — работающий Python нужной версии."""
    p = Path(path)
    if not p.exists():
        return False
    try:
        r = subprocess.run(
            [str(p), "-c",
             f"import sys; ok=sys.version_info>={min_ver!r}; "
             "print('ok' if ok else 'old')"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0 and r.stdout.strip() == "ok"
    except Exception:
        return False


def _first_valid(*candidates, min_ver=(3, 10)) -> str | None:
    for c in candidates:
        if c and _is_valid_python(c, min_ver):
            return str(c)
    return None


# ── Windows ───────────────────────────────────────────────────────────────────

def _find_python_windows() -> str:
    exe_dir = Path(sys.executable).parent

    # 1. Рядом с .exe
    for name in ("python.exe", "python3.exe",
                 "python313.exe", "python312.exe",
                 "python311.exe", "python310.exe"):
        found = _first_valid(exe_dir / name)
        if found:
            return found

    # 2. PATH (исключаем сам .exe)
    self_exe = Path(sys.executable).resolve()
    for name in ("python", "python3"):
        p = shutil.which(name)
        if p and Path(p).resolve() != self_exe:
            if _is_valid_python(p):
                return p

    # 3. Реестр
    try:
        import winreg
        hives = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
        subs = [
            r"SOFTWARE\Python\PythonCore",
            r"SOFTWARE\WOW6432Node\Python\PythonCore",
        ]
        for ver in ["3.13", "3.12", "3.11", "3.10"]:
            for hive in hives:
                for sub in subs:
                    for key_name in (f"{sub}\\{ver}\\InstallPath",):
                        try:
                            with winreg.OpenKey(hive, key_name) as k:
                                exe, _ = winreg.QueryValueEx(k, "ExecutablePath")
                                if exe and _is_valid_python(exe):
                                    return exe
                        except OSError:
                            pass
    except ImportError:
        pass

    # 4. Стандартные папки
    local_app = os.environ.get("LOCALAPPDATA", "")
    candidates: list[str] = []
    for v in ["313", "312", "311", "310"]:
        if local_app:
            candidates.append(
                rf"{local_app}\Programs\Python\Python{v}\python.exe")
    for pf in [r"C:\Program Files", r"C:\Program Files (x86)"]:
        for v in ["313", "312", "311", "310"]:
            candidates.append(rf"{pf}\Python{v}\python.exe")
    for v in ["313", "312", "311", "310"]:
        candidates.append(rf"C:\Python{v}\python.exe")
    # Microsoft Store / Winget
    if local_app:
        wa = rf"{local_app}\Microsoft\WindowsApps"
        for name in ["python3.exe", "python.exe"]:
            candidates.append(rf"{wa}\{name}")

    for c in candidates:
        if _is_valid_python(c):
            return c

    # 5. py.exe лаунчер
    py = shutil.which("py")
    if py:
        try:
            r = subprocess.run(
                [py, "-3", "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=5,
            )
            exe = r.stdout.strip()
            if _is_valid_python(exe):
                return exe
        except Exception:
            pass

    raise RuntimeError(
        "Python не найден.\n\n"
        "Переустановите LessonRecorder — установщик автоматически\n"
        "скачает Python. Или установите Python 3.10+ с python.org\n"
        "(включив «Add Python to PATH»)."
    )


# ── macOS ─────────────────────────────────────────────────────────────────────

def _find_python_macos() -> str:
    exe_dir = Path(sys.executable).parent

    # 1. Рядом с бандлом
    for name in ("python3", "python", "python3.13", "python3.12",
                 "python3.11", "python3.10"):
        found = _first_valid(exe_dir / name)
        if found:
            return found

    # 2. PATH
    self_exe = Path(sys.executable).resolve()
    for name in ("python3", "python"):
        p = shutil.which(name)
        if p and Path(p).resolve() != self_exe and _is_valid_python(p):
            return p

    # 3. Homebrew (Apple Silicon и Intel)
    brew_paths = [
        "/opt/homebrew/bin/python3",           # Apple Silicon
        "/opt/homebrew/bin/python3.13",
        "/opt/homebrew/bin/python3.12",
        "/opt/homebrew/bin/python3.11",
        "/opt/homebrew/bin/python3.10",
        "/usr/local/bin/python3",              # Intel
        "/usr/local/bin/python3.13",
        "/usr/local/bin/python3.12",
        "/usr/local/bin/python3.11",
        "/usr/local/bin/python3.10",
    ]
    found = _first_valid(*brew_paths)
    if found:
        return found

    # 4. pyenv
    pyenv_root = os.environ.get("PYENV_ROOT",
                                str(Path.home() / ".pyenv"))
    pyenv_shims = Path(pyenv_root) / "shims" / "python3"
    if pyenv_shims.exists() and _is_valid_python(pyenv_shims):
        # Resolve shim → реальный python
        try:
            r = subprocess.run(
                [str(pyenv_shims), "-c",
                 "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=5,
            )
            exe = r.stdout.strip()
            if _is_valid_python(exe):
                return exe
        except Exception:
            pass

    # Конкретные версии pyenv
    versions_dir = Path(pyenv_root) / "versions"
    if versions_dir.exists():
        for ver_dir in sorted(versions_dir.iterdir(), reverse=True):
            candidate = ver_dir / "bin" / "python3"
            if _is_valid_python(candidate):
                return str(candidate)

    # 5. Системный Python (macOS Ventura+)
    sys_paths = [
        "/usr/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
    ]
    found = _first_valid(*sys_paths)
    if found:
        return found

    raise RuntimeError(
        "Python 3.10+ не найден на Mac.\n\n"
        "Установите Python одним из способов:\n"
        "  • brew install python3\n"
        "  • Скачайте с python.org (macOS installer .pkg)\n"
        "  • pyenv install 3.12 && pyenv global 3.12"
    )


# ── Linux ─────────────────────────────────────────────────────────────────────

def _find_python_linux() -> str:
    exe_dir = Path(sys.executable).parent

    # 1. Рядом с бинарником (AppImage / portable)
    for name in ("python3", "python", "python3.12", "python3.11", "python3.10"):
        found = _first_valid(exe_dir / name)
        if found:
            return found

    # 2. PATH
    self_exe = Path(sys.executable).resolve()
    for name in ("python3", "python"):
        p = shutil.which(name)
        if p and Path(p).resolve() != self_exe and _is_valid_python(p):
            return p

    # 3. pyenv
    pyenv_root = os.environ.get("PYENV_ROOT",
                                str(Path.home() / ".pyenv"))
    versions_dir = Path(pyenv_root) / "versions"
    if versions_dir.exists():
        for ver_dir in sorted(versions_dir.iterdir(), reverse=True):
            candidate = ver_dir / "bin" / "python3"
            if _is_valid_python(candidate):
                return str(candidate)

    # 4. Стандартные системные пути
    system_paths = [
        "/usr/bin/python3",
        "/usr/bin/python3.12",
        "/usr/bin/python3.11",
        "/usr/bin/python3.10",
        "/usr/local/bin/python3",
        "/usr/local/bin/python3.12",
        "/usr/local/bin/python3.11",
        "/usr/local/bin/python3.10",
    ]
    found = _first_valid(*system_paths)
    if found:
        return found

    # 5. snap / flatpak обёртки
    snap_python = "/snap/bin/python3"
    if _is_valid_python(snap_python):
        return snap_python

    raise RuntimeError(
        "Python 3.10+ не найден.\n\n"
        "Установите Python:\n"
        "  • Ubuntu/Debian:  sudo apt install python3.12\n"
        "  • Fedora:         sudo dnf install python3.12\n"
        "  • Arch:           sudo pacman -S python\n"
        "  • Или pyenv:      https://github.com/pyenv/pyenv"
    )


# ── Публичный API ─────────────────────────────────────────────────────────────

def find_python_exe() -> str:
    """
    Возвращает путь к реальному интерпретатору Python (3.10+).
    В режиме разработки (не frozen) — просто sys.executable.
    Бросает RuntimeError с понятным сообщением если не найден.
    """
    if not getattr(sys, "frozen", False):
        return sys.executable

    platform = sys.platform
    if platform == "win32":
        return _find_python_windows()
    elif platform == "darwin":
        return _find_python_macos()
    else:
        return _find_python_linux()
