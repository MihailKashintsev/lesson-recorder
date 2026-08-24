"""
Утилита для поиска реального python.exe.

В PyInstaller-бандле sys.executable = LessonRecorder.exe, а не python.exe.
Запускать его с '-m pip' или '-c ...' открывает новое окно приложения.

Порядок поиска:
  1. Рядом с LessonRecorder.exe (позволяет положить python.exe вручную)
  2. PATH (исключая сам exe)
  3. Реестр Windows (HKCU/HKLM, версии 3.10–3.13)
  4. Стандартные папки установки Python (включая %LOCALAPPDATA%)
  5. Winget / Microsoft Store Python
"""
import sys
import os
import shutil
from pathlib import Path

MIN_PYTHON = (3, 10)


def _version_at_least(python_path: str, minimum: tuple[int, int]) -> bool:
    """Реально запускает python_path и проверяет sys.version_info — не полагаемся
    на то, что «python3» на PATH обязательно достаточно свежий (на macOS это
    сплошь и рядом древний Python 3.9 из Xcode Command Line Tools)."""
    try:
        import subprocess
        flags = 0
        if sys.platform == "win32":
            try: flags = subprocess.CREATE_NO_WINDOW
            except AttributeError: pass
        r = subprocess.run(
            [python_path, "-c",
             "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            capture_output=True, text=True, timeout=5, creationflags=flags,
        )
        major, minor = (int(x) for x in r.stdout.strip().split("."))
        return (major, minor) >= minimum
    except Exception:
        return False


def _check_exe(path: str | Path) -> str | None:
    """Проверяет что путь существует, это исполняемый файл, и версия Python
    не старше MIN_PYTHON (иначе pip install молча предлагает пакеты, которых
    для такой версии просто нет на PyPI)."""
    p = Path(path)
    if not p.exists() or p.suffix.lower() not in (".exe", ""):
        return None
    if not _version_at_least(str(p), MIN_PYTHON):
        return None
    return str(p)


def find_python_exe() -> str:
    """
    Возвращает путь к реальному python.exe.
    Если не найден — бросает RuntimeError с подробным объяснением.
    """
    # В режиме разработки — всё стандартно
    if not getattr(sys, "frozen", False):
        return sys.executable

    exe_dir = Path(sys.executable).parent

    # ── 1. Рядом с .exe (пользователь или установщик мог положить) ───────────
    for name in ("python.exe", "python3.exe",
                 "python313.exe", "python312.exe",
                 "python311.exe", "python310.exe"):
        found = _check_exe(exe_dir / name)
        if found:
            return found

    # ── 2. PATH ───────────────────────────────────────────────────────────────
    self_exe = Path(sys.executable).resolve()
    for name in ("python", "python3"):
        found_path = shutil.which(name)
        if found_path:
            resolved = Path(found_path).resolve()
            if resolved != self_exe:
                checked = _check_exe(found_path)
                if checked:
                    return checked

    # ── 2b. Стандартные папки macOS (Homebrew, python.org) ────────────────────
    if sys.platform == "darwin":
        mac_candidates = [
            "/opt/homebrew/bin/python3",   # Homebrew (Apple Silicon)
            "/usr/local/bin/python3",      # Homebrew (Intel)
        ]
        try:
            import glob
            mac_candidates += sorted(
                glob.glob("/Library/Frameworks/Python.framework/Versions/*/bin/python3"),
                reverse=True,
            )  # python.org installer
        except Exception:
            pass
        for c in mac_candidates:
            found = _check_exe(c)
            if found:
                return found

    # ── 3. Реестр Windows ─────────────────────────────────────────────────────
    try:
        import winreg
        hives = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
        subs  = [
            r"SOFTWARE\Python\PythonCore",
            r"SOFTWARE\WOW6432Node\Python\PythonCore",
        ]
        preferred = ["3.13", "3.12", "3.11", "3.10"]

        for ver in preferred:
            for hive in hives:
                for sub in subs:
                    key_path = rf"{sub}\{ver}\InstallPath"
                    try:
                        with winreg.OpenKey(hive, key_path) as k:
                            exe, _ = winreg.QueryValueEx(k, "ExecutablePath")
                            if exe and Path(exe).exists():
                                return exe
                    except OSError:
                        pass

                    # Попробуем ExecPrefix / (default) если ExecutablePath нет
                    try:
                        with winreg.OpenKey(hive, key_path) as k:
                            prefix, _ = winreg.QueryValueEx(k, "")
                            candidate = Path(prefix) / "python.exe"
                            if candidate.exists():
                                return str(candidate)
                    except OSError:
                        pass
    except ImportError:
        pass

    # ── 4. Стандартные папки Windows ──────────────────────────────────────────
    local_app = os.environ.get("LOCALAPPDATA", "")
    user_profile = os.environ.get("USERPROFILE", "")

    candidates: list[str] = []

    # %LOCALAPPDATA%\Programs\Python\PythonXYZ  (установка без прав админа)
    for v in ["313", "312", "311", "310"]:
        if local_app:
            candidates.append(rf"{local_app}\Programs\Python\Python{v}\python.exe")

    # %ProgramFiles%  (системная установка)
    for pf in [r"C:\Program Files", r"C:\Program Files (x86)"]:
        for v in ["313", "312", "311", "310"]:
            candidates.append(rf"{pf}\Python{v}\python.exe")
            candidates.append(rf"{pf}\Python\Python{v}\python.exe")

    # Корень диска C
    for v in ["313", "312", "311", "310"]:
        candidates.append(rf"C:\Python{v}\python.exe")

    # Winget установка (НЕ добавляем WindowsApps — там заглушки открывают окна!)
    if local_app:
        candidates.append(
            rf"{local_app}\Microsoft\WinGet\Packages"
            r"\Python.Python.3_Microsoft.Winget.Source_8wekyb3d8bbwe\python.exe"
        )

    for c in candidates:
        p = Path(c)
        if not p.exists():
            continue
        # Пропускаем заглушки Microsoft Store — они открывают окно магазина
        # вместо того чтобы запустить Python
        if "WindowsApps" in str(p):
            continue
        # Проверяем что файл больше 10 КБ (заглушки Store весят ~0 байт)
        try:
            if p.stat().st_size < 10240:
                continue
        except Exception:
            continue
        return c

    # ── 5. Последний шанс: py.exe лаунчер ────────────────────────────────────
    py_launcher = shutil.which("py")
    if py_launcher:
        try:
            import subprocess
            flags = 0
            if sys.platform == "win32":
                try: flags = subprocess.CREATE_NO_WINDOW
                except AttributeError: pass
            result = subprocess.run(
                [py_launcher, "-3", "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=5,
                creationflags=flags,
            )
            exe = result.stdout.strip()
            if exe and Path(exe).exists():
                # Тоже проверяем что не Store-заглушка
                if "WindowsApps" not in exe and Path(exe).stat().st_size > 10240:
                    return exe
        except Exception:
            pass

    if sys.platform == "darwin":
        raise RuntimeError(
            "Python не найден на этом компьютере.\n\n"
            "Решение:\n"
            "  1. Запустите mac_setup.sh из папки проекта — он сам поставит\n"
            "     Homebrew (если нужно) и Python.\n\n"
            "  2. Или установите Python вручную:\n"
            "     brew install python3\n"
            "     (либо скачайте с https://www.python.org/downloads/macos/)"
        )

    raise RuntimeError(
        "Python не найден на этом компьютере.\n\n"
        "Решение:\n"
        "  1. Переустановите LessonRecorder — установщик автоматически\n"
        "     скачает и установит Python.\n\n"
        "  2. Или установите Python вручную с python.org\n"
        "     (версия 3.10+, включить опцию 'Add Python to PATH')\n\n"
        f"  3. Или положите python.exe рядом с LessonRecorder.exe\n"
        f"     в папку: {exe_dir}"
    )