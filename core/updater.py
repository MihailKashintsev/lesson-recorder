"""
Автообновление LessonRecorder.

Подход вдохновлён ren3d-install.bat (github.com/MihailKashintsev/ren3d):
  — никакого PowerShell и его ExecutionPolicy
  — никакого VBScript и WMI (медленно и ненадёжно)
  — просто cmd.exe + timeout /t 3  →  запуск установщика
  — QTimer для отсчёта в UI (не блокирует главный поток)

Два пути:
  Portable .exe в релизе → копируем файл, UAC не нужен
  Setup .exe            → запускаем установщик, UAC всплывёт сам
"""
import os
import sys
import tempfile
import threading
import subprocess

import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QApplication,
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal

from version import __version__, APP_NAME, GITHUB_USER, GITHUB_REPO

API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
TIMEOUT = 10


# ── GitHub API ────────────────────────────────────────────────────────────────

def _get_latest_release() -> dict | None:
    try:
        r = requests.get(
            API_URL, timeout=TIMEOUT,
            headers={"Accept": "application/vnd.github+json"},
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _find_asset(release: dict) -> tuple[str, str, bool] | None:
    """
    Ищет .exe в assets релиза.
    Возвращает (name, url, is_portable).

    Приоритет (как в ren3d-install.bat):
      1. *portable*.exe  — не нужен UAC, просто заменяем файл
      2. *Setup*.exe / *installer*.exe
      3. любой другой .exe
    """
    assets = release.get("assets", [])

    for a in assets:
        if "portable" in a.get("name", "").lower() and a["name"].endswith(".exe"):
            return a["name"], a["browser_download_url"], True

    for a in assets:
        n = a.get("name", "").lower()
        if n.endswith(".exe") and ("setup" in n or "install" in n
                                   or n.startswith("lessonrecorder")):
            return a["name"], a["browser_download_url"], False

    for a in assets:
        if a.get("name", "").endswith(".exe"):
            return a["name"], a["browser_download_url"], False

    return None


# ── Поток скачивания ──────────────────────────────────────────────────────────

class DownloadThread(QThread):
    progress = pyqtSignal(int)   # 0–100
    finished = pyqtSignal(str)   # путь к файлу
    error    = pyqtSignal(str)

    def __init__(self, url: str, dest: str):
        super().__init__()
        self.url  = url
        self.dest = dest

    def run(self):
        try:
            r = requests.get(self.url, stream=True, timeout=180)
            r.raise_for_status()
            total      = int(r.headers.get("content-length", 0))
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


# ── Диалог обновления ─────────────────────────────────────────────────────────

class UpdateDialog(QDialog):
    def __init__(self, current: str, latest: str, changelog: str,
                 download_url: str, asset_name: str, is_portable: bool,
                 parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.asset_name   = asset_name
        self.is_portable  = is_portable
        self._downloader  = None
        self._countdown   = 3
        self._countdown_timer = None

        self.setWindowTitle(f"{APP_NAME} — Доступно обновление")
        self.setFixedWidth(500)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet("""
            QDialog { background: #1a1a1a; color: #e0e0e0; }
            QLabel  { color: #e0e0e0; }
        """)
        self._build_ui(current, latest, changelog)

    def _build_ui(self, current, latest, changelog):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 28)

        ico = QLabel("🔄")
        ico.setStyleSheet("font-size: 36px;")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ico)

        title = QLabel(f"Доступна новая версия {APP_NAME}!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        ver = QLabel(f"Текущая: <b>{current}</b>  →  Новая: <b>{latest}</b>")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("color: #aaa; font-size: 13px;")
        ver.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(ver)

        # Плашка типа обновления
        if self.is_portable:
            badge_text  = "✅ Портативная версия — установка без прав администратора"
            badge_color = "#4caf50"
            badge_bg    = "#0d2a0d"
        else:
            badge_text  = "ℹ️ Полный установщик — потребуется подтверждение UAC"
            badge_color = "#ffb300"
            badge_bg    = "#2a1f00"

        badge = QLabel(badge_text)
        badge.setStyleSheet(
            f"color: {badge_color}; font-size: 11px;"
            f" background: {badge_bg}; border-radius: 5px; padding: 5px 10px;"
        )
        badge.setWordWrap(True)
        layout.addWidget(badge)

        if changelog:
            notes = QLabel(changelog[:500] + ("…" if len(changelog) > 500 else ""))
            notes.setWordWrap(True)
            notes.setStyleSheet(
                "background: #111; border-radius: 6px; padding: 10px;"
                " color: #aaa; font-size: 12px;"
            )
            layout.addWidget(notes)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar         { border: none; background: #2a2a2a; border-radius: 3px; }
            QProgressBar::chunk  { background: #4a9eff; border-radius: 3px; }
        """)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()

        self.skip_btn = QPushButton("Пропустить")
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background: #2a2a2a; color: #888;
                border: 1px solid #3a3a3a; border-radius: 8px; padding: 8px 20px;
            }
            QPushButton:hover { background: #333; color: #ccc; }
        """)
        self.skip_btn.clicked.connect(self.reject)

        self.update_btn = QPushButton("⬇  Скачать и установить")
        self.update_btn.setStyleSheet("""
            QPushButton {
                background: #4a9eff; color: white;
                border: none; border-radius: 8px;
                padding: 8px 20px; font-weight: bold;
            }
            QPushButton:hover    { background: #5aadff; }
            QPushButton:disabled { background: #1a3a5a; color: #555; }
        """)
        self.update_btn.clicked.connect(self._start_download)

        btn_row.addWidget(self.skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.update_btn)
        layout.addLayout(btn_row)

    # ── Скачивание ────────────────────────────────────────────────────────

    def _start_download(self):
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Скачиваю обновление…")

        tmp_dir   = tempfile.mkdtemp(prefix="lr_update_")
        dest_path = os.path.join(tmp_dir, self.asset_name)

        self._downloader = DownloadThread(self.download_url, dest_path)
        self._downloader.progress.connect(self.progress_bar.setValue)
        self._downloader.finished.connect(self._on_downloaded)
        self._downloader.error.connect(self._on_error)
        self._downloader.start()

    def _on_downloaded(self, new_exe: str):
        """
        Подход из ren3d-install.bat:
          cmd.exe + timeout /t 3 — самый простой и надёжный способ на Windows.
          Никакого PowerShell, никакого WMI, никаких политик исполнения.

        Portable: копируем новый exe поверх текущего, запускаем.
        Installer: просто запускаем — UAC сам всплывёт.
        """
        cur_exe = sys.executable
        tmp_bat  = os.path.join(tempfile.gettempdir(), "lr_update.bat")

        if self.is_portable:
            # Portable: копируем файл и перезапускаем без UAC
            bat = (
                "@echo off\r\n"
                "timeout /t 3 /nobreak > nul\r\n"
                f'copy /Y "{new_exe}" "{cur_exe}" > nul\r\n'
                f'start "" "{cur_exe}"\r\n'
            )
        else:
            # Installer: запускаем setup-файл (/RESTARTAPPLICATIONS — InnoSetup перезапустит сам)
            bat = (
                "@echo off\r\n"
                "timeout /t 3 /nobreak > nul\r\n"
                f'"{new_exe}" /SILENT /RESTARTAPPLICATIONS\r\n'
            )

        with open(tmp_bat, "w", encoding="cp1251") as f:
            f.write(bat)

        # Запускаем cmd ОТДЕЛЬНЫМ процессом — без close_fds (блокирует UI!)
        # /min — свёрнутое окно, не пугает пользователя
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "/min", "", "cmd.exe", "/c", tmp_bat],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )

        # QTimer отсчёт — НЕ блокируем главный поток
        self.skip_btn.setEnabled(False)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick)
        self._countdown_timer.start()
        self._tick()  # показываем сразу, не ждём первой секунды

    def _tick(self):
        if self._countdown > 0:
            if self.is_portable:
                msg = f"✅ Скачано! Закрываю через {self._countdown}с — обновление применится автоматически"
            else:
                msg = f"✅ Скачано! Закрываю через {self._countdown}с — установщик запустится автоматически"
            self.status_label.setText(msg)
            self.status_label.setStyleSheet("color: #4caf50; font-size: 12px;")
            self._countdown -= 1
        else:
            self._countdown_timer.stop()
            QApplication.quit()

    def _on_error(self, msg: str):
        self.status_label.setText(f"❌ {msg}")
        self.status_label.setStyleSheet("color: #f44336; font-size: 12px;")
        self.update_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.progress_bar.setVisible(False)


# ── Публичный API ─────────────────────────────────────────────────────────────

def check_for_updates(parent=None, silent_if_latest: bool = True):
    """Проверяет обновления. Если найдено — показывает диалог."""
    release = _get_latest_release()
    if not release:
        return

    latest_tag = release.get("tag_name", "").lstrip("v")
    try:
        from packaging.version import Version
        if Version(latest_tag) <= Version(__version__):
            return
    except Exception:
        return

    asset = _find_asset(release)
    if not asset:
        return

    asset_name, download_url, is_portable = asset
    changelog = release.get("body", "")

    dlg = UpdateDialog(
        current      = __version__,
        latest       = latest_tag,
        changelog    = changelog,
        download_url = download_url,
        asset_name   = asset_name,
        is_portable  = is_portable,
        parent       = parent,
    )
    dlg.exec()


def check_for_updates_async(parent=None):
    """Проверяет обновления в фоне — не блокирует запуск приложения."""
    def _worker():
        import time
        time.sleep(2)   # дать приложению запуститься
        check_for_updates(parent, silent_if_latest=True)

    threading.Thread(target=_worker, daemon=True).start()
