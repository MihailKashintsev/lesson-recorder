"""
Утилита для поиска реального python.exe.

В PyInstaller-бандле sys.executable = LessonRecorder.exe, а не python.exe.
Запускать его с '-m pip' или '-c ...' открывает новое окно приложения.
"""
import sys
import shutil
from pathlib import Path


def find_python_exe() -> str:
    """
    Возвращает путь к реальному python.exe.
    Если не найден — бросает RuntimeError.
    """
    # Не PyInstaller — всё стандартно
    if not getattr(sys, "frozen", False):
        return sys.executable

    # PyInstaller frozen — ищем python.exe
    exe_dir = Path(sys.executable).parent

    # 1. Рядом с .exe приложения
    for name in ("python.exe", "python3.exe",
                 "python313.exe", "python312.exe", "python311.exe", "python310.exe"):
        c = exe_dir / name
        if c.exists():
            return str(c)

    # 2. PATH (исключаем себя)
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found:
            p = Path(found).resolve()
            if p != Path(sys.executable).resolve():
                return str(p)

    # 3. Реестр Windows
    try:
        import winreg
        for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            for sub in [r"SOFTWARE\Python\PythonCore",
                        r"SOFTWARE\WOW6432Node\Python\PythonCore"]:
                try:
                    with winreg.OpenKey(hive, sub) as key:
                        n, _, _ = winreg.QueryInfoKey(key)
                        for i in range(n):
                            ver = winreg.EnumKey(key, i)
                            try:
                                with winreg.OpenKey(key, rf"{ver}\InstallPath") as kp:
                                    exe, _ = winreg.QueryValueEx(kp, "ExecutablePath")
                                    if exe and Path(exe).exists():
                                        return exe
                            except OSError:
                                pass
                except OSError:
                    pass
    except ImportError:
        pass

    # 4. Стандартные пути
    for p in [
        r"C:\Python313\python.exe", r"C:\Python312\python.exe",
        r"C:\Python311\python.exe", r"C:\Python310\python.exe",
        r"C:\Users\Public\Python\python.exe",
    ]:
        if Path(p).exists():
            return p

    raise RuntimeError(
        "Не удалось найти python.exe.\n"
        "Убедись что Python установлен и доступен в PATH,\n"
        "или положи python.exe рядом с LessonRecorder.exe."
    )
