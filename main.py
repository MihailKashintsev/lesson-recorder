import sys
import os
import traceback

# Устанавливаем ДО любого импорта ctranslate2/faster_whisper
os.environ["CT2_FORCE_CPU_ISA"] = "SSE2"
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

# ── Режим воркера транскрипции ─────────────────────────────────────────────
if "--transcribe-worker" in sys.argv:
    idx = sys.argv.index("--transcribe-worker")
    sys.argv = [sys.argv[0]] + sys.argv[idx + 1:]
    from core.transcribe_worker import main as _worker_main
    _worker_main()
    sys.exit(0)


# ── Кросс-платформенные флаги subprocess ──────────────────────────────────
def _subprocess_flags() -> int:
    """CREATE_NO_WINDOW только на Windows, на других платформах = 0."""
    if sys.platform == "win32":
        try:
            import subprocess
            return subprocess.CREATE_NO_WINDOW
        except AttributeError:
            return 0x08000000   # fallback значение
    return 0


_SP_FLAGS = _subprocess_flags()


# ── Обязательные пакеты ───────────────────────────────────────────────────
REQUIRED = [
    ("faster_whisper", "faster-whisper"),
    ("whisper",        "openai-whisper"),
    ("numpy",          "numpy"),
    ("scipy",          "scipy"),
    ("sounddevice",    "sounddevice"),
    ("requests",       "requests"),
    ("openai",         "openai"),
]


def _pip_show_installed(pip_name: str) -> bool:
    """
    Проверяет установку через 'pip show'.
    Надёжнее importlib.util.find_spec в frozen-режиме.
    """
    import subprocess
    try:
        from core.python_path import find_python_exe
        python = find_python_exe()
    except Exception:
        python = sys.executable
        if getattr(sys, "frozen", False):
            return True   # Не блокируем запуск

    try:
        r = subprocess.run(
            [python, "-m", "pip", "show", pip_name],
            capture_output=True, text=True, timeout=10,
            creationflags=_SP_FLAGS,
        )
        if r.returncode != 0:
            return False
        for line in r.stdout.splitlines():
            if line.startswith("Location:"):
                loc = line.split(":", 1)[1].strip()
                if "_internal" in loc.replace("\\", "/"):
                    return False
        return True
    except Exception:
        return True


def _missing_packages():
    from concurrent.futures import ThreadPoolExecutor
    results = []
    with ThreadPoolExecutor(max_workers=7) as ex:
        futures = {ex.submit(_pip_show_installed, pip): (imp, pip)
                   for imp, pip in REQUIRED}
        for fut, (imp, pip) in futures.items():
            try:
                if not fut.result(timeout=15):
                    results.append((imp, pip))
            except Exception:
                pass
    return results


def _pip_install(pip_name: str) -> bool:
    import subprocess
    if getattr(sys, "frozen", False):
        return False
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_name,
             "--quiet", "--disable-pip-version-check"],
            capture_output=True, text=True, timeout=300,
            creationflags=_SP_FLAGS,
        )
        return r.returncode == 0
    except Exception:
        return False


def _autoinstall_qt(app, missing):
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame,
    )
    from PyQt6.QtCore import QThread, pyqtSignal, Qt

    class Worker(QThread):
        pkg_done = pyqtSignal(str, bool)
        all_done = pyqtSignal(list)

        def __init__(self, pkgs):
            super().__init__()
            self.pkgs = pkgs

        def run(self):
            failed = []
            for _, pip_name in self.pkgs:
                ok = _pip_install(pip_name)
                if not ok:
                    failed.append(pip_name)
                self.pkg_done.emit(pip_name, ok)
            self.all_done.emit(failed)

    dlg = QDialog()
    dlg.setWindowTitle("LessonRecorder — Установка")
    dlg.setMinimumWidth(480)
    dlg.setFixedWidth(480)
    dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
    dlg.setStyleSheet("""
        QDialog { background: #0d1117; color: #e6edf3; border-radius: 12px; }
        QLabel  { color: #e6edf3; background: transparent; }
    """)

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(32, 32, 32, 32)
    lay.setSpacing(0)

    lbl_title = QLabel("⚙️  Первый запуск")
    lbl_title.setStyleSheet(
        "font-size:18px; font-weight:700; color:#e6edf3; margin-bottom:6px;")
    lay.addWidget(lbl_title)

    lbl_sub = QLabel("Устанавливаю необходимые компоненты…")
    lbl_sub.setStyleSheet("color:#8b949e; font-size:13px;")
    lay.addWidget(lbl_sub)
    lay.addSpacing(24)

    pbar = QProgressBar()
    pbar.setRange(0, max(len(missing), 1))
    pbar.setValue(0)
    pbar.setFixedHeight(22)
    pbar.setFormat("%p%  (%v / %m)")
    pbar.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pbar.setStyleSheet("""
        QProgressBar {
            border: none; background: #21262d; border-radius: 11px;
            color: #e6edf3; font-size: 11px; font-weight: 600;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #58a6ff, stop:1 #bc8cff);
            border-radius: 11px;
        }
    """)
    lay.addWidget(pbar)
    lay.addSpacing(12)

    status = QLabel(f"↓  {missing[0][1]}" if missing else "")
    status.setStyleSheet("color:#8b949e; font-size:12px;")
    lay.addWidget(status)

    lay.addSpacing(16)
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet("color:#21262d;")
    lay.addWidget(sep)
    lay.addSpacing(10)

    pkg_labels: dict[str, tuple] = {}
    for _, pip_name in missing:
        row = QHBoxLayout()
        dot = QLabel("○")
        dot.setFixedWidth(16)
        dot.setStyleSheet("color:#484f58; font-size:12px;")
        name = QLabel(pip_name)
        name.setStyleSheet("color:#8b949e; font-size:12px;")
        row.addWidget(dot)
        row.addWidget(name)
        row.addStretch()
        pkg_labels[pip_name] = (dot, name)
        lay.addLayout(row)

    done_count = [0]
    failed_out = [[]]

    def on_pkg(pip_name, ok):
        done_count[0] += 1
        pbar.setValue(done_count[0])
        idx = done_count[0]
        nxt = missing[idx][1] if idx < len(missing) else ""
        icon = "✅" if ok else "❌"
        color = "#3fb950" if ok else "#f85149"
        if pip_name in pkg_labels:
            dot, name = pkg_labels[pip_name]
            dot.setText(icon)
            dot.setStyleSheet(f"font-size:12px; color:{color};")
            name.setStyleSheet(f"color:{color}; font-size:12px;")
        status.setText(f"↓  {nxt}" if nxt else "✅  Готово")

    def on_all(failed):
        failed_out[0] = failed
        dlg.accept()

    w = Worker(missing)
    w.pkg_done.connect(on_pkg)
    w.all_done.connect(on_all)
    w.start()
    dlg.exec()
    w.wait(5000)
    return failed_out[0]


# ─────────────────────────────────────────────────────────────────────────────

def _set_app_id():
    """Windows AppUserModelID — иконка на панели задач."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "LessonRecorder.App.1")
    except Exception:
        pass


def _set_macos_app_name():
    """Имя приложения в меню macOS."""
    if sys.platform != "darwin":
        return
    try:
        # Имя в системном меню берётся из CFBundleName, но можно переопределить
        os.environ.setdefault("APPNAME", "LessonRecorder")
    except Exception:
        pass


def main():
    _set_app_id()
    _set_macos_app_name()
    missing = _missing_packages()

    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtGui import QIcon
        from PyQt6.QtCore import QTimer
    except ImportError:
        print("ОШИБКА: PyQt6 не установлен.")
        print("Выполни: pip install -r requirements.txt")
        try:
            input("Нажми Enter для выхода...")
        except EOFError:
            pass
        sys.exit(1)

    # На macOS нужно разрешить high-DPI для ретина-экранов
    if sys.platform == "darwin":
        os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")

    app = QApplication(sys.argv)

    if missing:
        if getattr(sys, "frozen", False):
            names = ", ".join(p for _, p in missing)
            QMessageBox.warning(
                None, "Отсутствуют пакеты",
                f"Не установлены: {names}\n\n"
                "Транскрипция может не работать.\n"
                "Открой Настройки → Пакеты для управления.",
            )
        else:
            failed = _autoinstall_qt(app, missing)
            if failed:
                QMessageBox.warning(
                    None, "Не удалось установить",
                    f"Пакеты не установлены: {', '.join(failed)}\n\n"
                    "Открой Настройки → Пакеты и попробуй вручную.",
                )

    def handle_exc(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        err = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print("КРИТИЧЕСКАЯ ОШИБКА:\n", err)
        try:
            QMessageBox().setDetailedText(err)
        except Exception:
            pass

    sys.excepthook = handle_exc

    try:
        import core.database as db
        db.init_db()
    except Exception as e:
        QMessageBox.critical(
            None, "Ошибка БД",
            f"Не удалось инициализировать базу данных:\n{e}",
        )
        sys.exit(1)

    try:
        from version import __version__, APP_NAME
    except ImportError:
        __version__ = "dev"
        APP_NAME = "LessonRecorder"

    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)

    # ── Иконка приложения (кросс-платформа) ──────────────────────────────
    try:
        from pathlib import Path
        base = Path(sys._MEIPASS) if getattr(sys, "_MEIPASS", None) else Path(__file__).parent

        # Windows → .ico, macOS → .icns, Linux → .png
        icon_names = {
            "win32":  ["app_icon.ico", "app_icon.png"],
            "darwin": ["app_icon.icns", "app_icon.png"],
        }.get(sys.platform, ["app_icon.png", "app_icon.ico"])

        candidates = []
        for name in icon_names:
            candidates += [
                base / name,
                Path(__file__).parent / name,
                Path(sys.executable).parent / name,
            ]

        for icon_path in candidates:
            if icon_path.exists():
                app.setWindowIcon(QIcon(str(icon_path)))
                break
    except Exception:
        pass

    try:
        from ui.main_window import MainWindow
        window = MainWindow()
        window.show()
    except Exception as e:
        QMessageBox.critical(
            None, "Ошибка запуска",
            f"Не удалось открыть главное окно:\n\n{e}\n\n{traceback.format_exc()}",
        )
        sys.exit(1)

    def _check_updates():
        try:
            from core.updater import check_for_updates_async
            check_for_updates_async(parent=window)
        except Exception:
            pass

    QTimer.singleShot(4000, _check_updates)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()