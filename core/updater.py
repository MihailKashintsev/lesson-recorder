"""
Проверяет наличие обновлений на GitHub Releases.
Если найдена новая версия — предлагает скачать и установить.
"""
import os
import sys
import tempfile
import threading
import subprocess
from packaging.version import Version

import requests
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QApplication
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from version import __version__, APP_NAME, GITHUB_USER, GITHUB_REPO

API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
TIMEOUT = 10


def _get_latest_release() -> dict | None:
    """Возвращает dict с данными последнего релиза или None при ошибке."""
    try:
        r = requests.get(API_URL, timeout=TIMEOUT,
                         headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _find_installer_asset(release: dict) -> tuple[str, str] | None:
    """Ищет .exe файл установщика в assets релиза. Возвращает (name, download_url)."""
    for asset in release.get("assets", []):
        name: str = asset.get("name", "")
        if name.lower().endswith("_setup.exe") or name.lower().startswith("lessonrecorder") and name.endswith(".exe"):
            return name, asset["browser_download_url"]
    # fallback — первый .exe
    for asset in release.get("assets", []):
        if asset.get("name", "").endswith(".exe"):
            return asset["name"], asset["browser_download_url"]
    return None


class DownloadThread(QThread):
    progress = pyqtSignal(int)       # 0-100
    finished = pyqtSignal(str)       # path to downloaded file
    error = pyqtSignal(str)

    def __init__(self, url: str, dest: str):
        super().__init__()
        self.url = url
        self.dest = dest

    def run(self):
        try:
            r = requests.get(self.url, stream=True, timeout=120)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(self.dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(int(downloaded / total * 100))
            self.finished.emit(self.dest)
        except Exception as e:
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    def __init__(self, current: str, latest: str, changelog: str, download_url: str,
                 asset_name: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.asset_name = asset_name
        self._downloader = None
        self._dest = None

        self.setWindowTitle(f"{APP_NAME} — Доступно обновление")
        self.setFixedWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("""
            QDialog { background: #1a1a1a; color: #e0e0e0; }
            QLabel  { color: #e0e0e0; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 28)

        # Header
        ico = QLabel("🔄")
        ico.setStyleSheet("font-size: 36px;")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ico)

        title = QLabel(f"Доступна новая версия {APP_NAME}!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        version_info = QLabel(f"Текущая версия: <b>{current}</b>  →  Новая: <b>{latest}</b>")
        version_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_info.setStyleSheet("color: #aaa; font-size: 13px;")
        version_info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(version_info)

        # Changelog
        if changelog:
            notes_label = QLabel("Что нового:")
            notes_label.setStyleSheet("font-weight: bold; color: #ccc; margin-top: 8px;")
            layout.addWidget(notes_label)

            changelog_text = QLabel(changelog[:600] + ("…" if len(changelog) > 600 else ""))
            changelog_text.setWordWrap(True)
            changelog_text.setStyleSheet(
                "background: #111; border-radius: 6px; padding: 10px; "
                "color: #aaa; font-size: 12px;"
            )
            layout.addWidget(changelog_text)

        # Progress bar (hidden until download starts)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: none; background: #2a2a2a; border-radius: 3px; }
            QProgressBar::chunk { background: #4a9eff; border-radius: 3px; }
        """)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_row = QHBoxLayout()
        self.skip_btn = QPushButton("Пропустить")
        self.skip_btn.setStyleSheet("""
            QPushButton { background: #2a2a2a; color: #888; border: 1px solid #3a3a3a;
                          border-radius: 8px; padding: 8px 20px; }
            QPushButton:hover { background: #333; color: #ccc; }
        """)
        self.skip_btn.clicked.connect(self.reject)

        self.update_btn = QPushButton("⬇  Скачать и установить")
        self.update_btn.setStyleSheet("""
            QPushButton { background: #4a9eff; color: white; border: none;
                          border-radius: 8px; padding: 8px 20px; font-weight: bold; }
            QPushButton:hover { background: #5aadff; }
            QPushButton:disabled { background: #2a4a6a; color: #666; }
        """)
        self.update_btn.clicked.connect(self._start_download)

        btn_row.addWidget(self.skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.update_btn)
        layout.addLayout(btn_row)

    def _start_download(self):
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Скачиваю обновление…")

        tmp_dir = tempfile.mkdtemp()
        self._dest = os.path.join(tmp_dir, self.asset_name)

        self._downloader = DownloadThread(self.download_url, self._dest)
        self._downloader.progress.connect(self.progress_bar.setValue)
        self._downloader.finished.connect(self._on_downloaded)
        self._downloader.error.connect(self._on_error)
        self._downloader.start()

    def _on_downloaded(self, path: str):
        self.status_label.setText("Запускаю установщик…")
        # Run installer silently and exit the app
        subprocess.Popen([path, "/SILENT", "/CLOSEAPPLICATIONS"],
                         creationflags=subprocess.DETACHED_PROCESS
                         if sys.platform == "win32" else 0)
        QApplication.quit()

    def _on_error(self, msg: str):
        self.status_label.setText(f"Ошибка: {msg}")
        self.update_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)


def check_for_updates(parent=None, silent_if_latest: bool = True):
    """
    Проверяет обновления. Если найдено — показывает диалог.
    silent_if_latest=True — не показывает диалог если уже актуальная версия.
    """
    release = _get_latest_release()
    if not release:
        return  # нет интернета или ошибка — молча игнорируем

    latest_tag = release.get("tag_name", "").lstrip("v")
    try:
        if Version(latest_tag) <= Version(__version__):
            return  # уже актуальная версия
    except Exception:
        return

    asset = _find_installer_asset(release)
    if not asset:
        return  # в релизе нет .exe

    asset_name, download_url = asset
    changelog = release.get("body", "")

    dialog = UpdateDialog(
        current=__version__,
        latest=latest_tag,
        changelog=changelog,
        download_url=download_url,
        asset_name=asset_name,
        parent=parent,
    )
    dialog.exec()


def check_for_updates_async(parent=None):
    """Проверяет обновления в фоновом потоке, не блокируя запуск приложения."""
    def _worker():
        import time
        time.sleep(2)  # дать приложению запуститься
        from PyQt6.QtCore import QMetaObject, Qt
        check_for_updates(parent, silent_if_latest=True)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
