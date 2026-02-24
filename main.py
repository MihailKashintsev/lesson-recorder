import sys
import os
import traceback

# Устанавливаем ДО любого импорта ctranslate2/faster_whisper
os.environ["CT2_FORCE_CPU_ISA"] = "SSE2"
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

# ── Режим воркера транскрипции ────────────────────────────────────────────────
# Когда frozen .exe вызывается с флагом --transcribe-worker,
# работаем как subprocess-воркер без GUI.
if "--transcribe-worker" in sys.argv:
    idx = sys.argv.index("--transcribe-worker")
    # Убираем флаг, передаём остальные аргументы воркеру
    sys.argv = [sys.argv[0]] + sys.argv[idx + 1:]
    from core.transcribe_worker import main as _worker_main
    _worker_main()
    sys.exit(0)


# ── Обязательные пакеты ───────────────────────────────────────────────────────
REQUIRED = [
    ("faster_whisper", "faster-whisper"),
    ("numpy",          "numpy"),
    ("scipy",          "scipy"),
    ("sounddevice",    "sounddevice"),
    ("requests",       "requests"),
    ("openai",         "openai"),
]


def _missing_packages():
    import importlib, importlib.util
    importlib.invalidate_caches()
    return [
        (imp, pip) for imp, pip in REQUIRED
        if importlib.util.find_spec(imp.split(".")[0]) is None
    ]


def _pip_install(pip_name: str) -> bool:
    """Устанавливает пакет через pip. Возвращает True при успехе."""
    import subprocess

    # В frozen-режиме sys.executable = само приложение, pip запускать нельзя.
    # Пропускаем и показываем сообщение пользователю.
    if getattr(sys, "frozen", False):
        return False

    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW

    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_name,
             "--quiet", "--disable-pip-version-check"],
            capture_output=True, text=True, timeout=300,
            creationflags=flags,
        )
        return r.returncode == 0
    except Exception:
        return False


def _autoinstall_qt(app, missing):
    """Диалог установки пакетов при первом запуске."""
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
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
    dlg.setWindowTitle("LessonRecorder — Первый запуск")
    dlg.setMinimumWidth(400)
    dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
    dlg.setStyleSheet("QDialog{background:#141414;color:#e0e0e0;} QLabel{color:#e0e0e0;background:transparent;}")

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(28, 28, 28, 28)
    lay.setSpacing(14)

    lay.addWidget(QLabel("⚙️  Первый запуск",
                         styleSheet="font-size:16px;font-weight:700;"))
    lay.addWidget(QLabel("Устанавливаю необходимые компоненты…",
                         styleSheet="color:#888;font-size:13px;"))

    pbar = QProgressBar()
    pbar.setRange(0, len(missing))
    pbar.setValue(0)
    pbar.setFixedHeight(8)
    pbar.setStyleSheet(
        "QProgressBar{border:none;background:#252525;border-radius:4px;}"
        "QProgressBar::chunk{background:#4a9eff;border-radius:4px;}"
    )
    lay.addWidget(pbar)

    status = QLabel(f"Скачиваю {missing[0][1]}…" if missing else "")
    status.setStyleSheet("color:#888;font-size:12px;")
    lay.addWidget(status)

    done_count = [0]
    failed_out = [[]]

    def on_pkg(pip_name, ok):
        done_count[0] += 1
        pbar.setValue(done_count[0])
        idx = done_count[0]
        nxt = missing[idx][1] if idx < len(missing) else ""
        status.setText(
            f"{'✅' if ok else '❌'} {pip_name}"
            + (f"   →   Скачиваю {nxt}…" if nxt else "")
        )

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

def main():
    missing = _missing_packages()

    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtGui import QIcon
        from PyQt6.QtCore import QTimer
    except ImportError:
        print("ОШИБКА: PyQt6 не установлен. Выполни: pip install -r requirements.txt")
        input("Нажми Enter для выхода...")
        sys.exit(1)

    app = QApplication(sys.argv)

    if missing:
        if getattr(sys, "frozen", False):
            # В .exe нельзя устанавливать пакеты — просто предупреждаем
            names = ", ".join(p for _, p in missing)
            QMessageBox.warning(None, "Отсутствуют пакеты",
                f"Не установлены: {names}\n\n"
                "Транскрипция может не работать.\n"
                "Открой Настройки → Пакеты для управления.")
        else:
            failed = _autoinstall_qt(app, missing)
            if failed:
                QMessageBox.warning(None, "Не удалось установить",
                    f"Пакеты не установлены: {', '.join(failed)}\n\n"
                    "Открой Настройки → Пакеты и попробуй вручную.")

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
        QMessageBox.critical(None, "Ошибка БД",
                             f"Не удалось инициализировать базу данных:\n{e}")
        sys.exit(1)

    try:
        from version import __version__, APP_NAME
    except ImportError:
        __version__ = "dev"
        APP_NAME    = "LessonRecorder"

    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)

    try:
        from pathlib import Path
        icon = Path(__file__).parent / "app_icon.ico"
        if icon.exists():
            app.setWindowIcon(QIcon(str(icon)))
    except Exception:
        pass

    try:
        from ui.main_window import MainWindow
        window = MainWindow()
        window.show()
    except Exception as e:
        QMessageBox.critical(None, "Ошибка запуска",
            f"Не удалось открыть главное окно:\n\n{e}\n\n{traceback.format_exc()}")
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
