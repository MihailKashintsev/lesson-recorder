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


def _check_exe(path: str | Path) -> str | None:
    """Проверяет что путь существует и это исполняемый файл Python."""
    p = Path(path)
    if p.exists() and p.suffix.lower() in (".exe", ""):
        return str(p)
    return None


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
                return str(found_path)

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

    # Microsoft Store Python (%LOCALAPPDATA%\Microsoft\WindowsApps)
    if local_app:
        wa = rf"{local_app}\Microsoft\WindowsApps"
        for name in ["python3.exe", "python.exe",
                     "python3.13.exe", "python3.12.exe",
                     "python3.11.exe", "python3.10.exe"]:
            candidates.append(rf"{wa}\{name}")

    # Winget установка
    if local_app:
        candidates.append(
            rf"{local_app}\Microsoft\WinGet\Packages"
            r"\Python.Python.3_Microsoft.Winget.Source_8wekyb3d8bbwe\python.exe"
        )

    for c in candidates:
        if Path(c).exists():
            return c

    # ── 5. Последний шанс: py.exe лаунчер ────────────────────────────────────
    py_launcher = shutil.which("py")
    if py_launcher:
        try:
            import subprocess
            result = subprocess.run(
                [py_launcher, "-3", "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=5
            )
            exe = result.stdout.strip()
            if exe and Path(exe).exists():
                return exe
        except Exception:
            pass

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
