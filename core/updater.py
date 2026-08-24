"""
Автообновление LessonRecorder — кросс-платформенный.

Windows : скачивает .exe установщик, запускает через cmd.exe bat-файл
macOS   : скачивает .zip, распаковывает, открывает Finder + инструкция
Linux   : скачивает .AppImage или .tar.gz, открывает папку + инструкция
"""
import os
import sys
import platform
import tempfile
import subprocess
import webbrowser

import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QScrollArea, QWidget, QFrame,
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

from version import __version__, APP_NAME, GITHUB_USER, GITHUB_REPO

API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
TIMEOUT = 10


# ── Определение платформы ────────────────────────────────────────────────────

def _platform() -> str:
    """win | mac_arm | mac_x64 | linux"""
    if sys.platform == "win32":
        return "win"
    if sys.platform == "darwin":
        if platform.machine() == "arm64":
            return "mac_arm"
        return "mac_x64"
    return "linux"


def _platform_label() -> str:
    p = _platform()
    return {
        "win":     "Windows",
        "mac_arm": "macOS (Apple Silicon)",
        "mac_x64": "macOS (Intel)",
        "linux":   "Linux",
    }[p]


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
    Возвращает (asset_name, download_url, is_portable) для текущей платформы.
    """
    assets = release.get("assets", [])
    p = _platform()

    def _match(name: str, *keywords) -> bool:
        n = name.lower()
        return all(k in n for k in keywords)

    if p == "win":
        # Сначала портативная, потом установщик
        for a in assets:
            if _match(a["name"], "portable") and a["name"].endswith(".exe"):
                return a["name"], a["browser_download_url"], True
        for a in assets:
            n = a["name"]
            if n.endswith(".exe") and ("setup" in n.lower() or "install" in n.lower()
                                        or n.lower().startswith("lessonrecorder")):
                return n, a["browser_download_url"], False
        for a in assets:
            if a["name"].endswith(".exe"):
                return a["name"], a["browser_download_url"], False

    elif p == "mac_arm":
        for a in assets:
            if _match(a["name"], "arm64") and a["name"].endswith(".zip"):
                return a["name"], a["browser_download_url"], False
        for a in assets:
            if _match(a["name"], "macos") and a["name"].endswith(".zip"):
                return a["name"], a["browser_download_url"], False

    elif p == "mac_x64":
        for a in assets:
            if (_match(a["name"], "x64") or _match(a["name"], "intel")) \
                    and a["name"].endswith(".zip"):
                return a["name"], a["browser_download_url"], False
        for a in assets:
            if _match(a["name"], "macos") and a["name"].endswith(".zip"):
                return a["name"], a["browser_download_url"], False

    elif p == "linux":
        for a in assets:
            if a["name"].endswith(".AppImage"):
                return a["name"], a["browser_download_url"], False
        for a in assets:
            if a["name"].endswith(".tar.gz") and "linux" in a["name"].lower():
                return a["name"], a["browser_download_url"], False

    return None


# ── Вспомогательные виджеты ──────────────────────────────────────────────────

def _card(text: str, bg: str, border: str, text_color: str = "#e0e0e0") -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setStyleSheet(
        f"background:{bg}; border:1px solid {border}; border-radius:10px;"
        f" padding:14px 16px; color:{text_color}; font-size:12px; line-height:1.5;"
    )
    return lbl


def _step_card(steps: list[str], title: str = "") -> QWidget:
    """Нумерованные шаги в карточке."""
    w = QWidget()
    w.setStyleSheet(
        "background:#111a11; border:1px solid #2a4a2a;"
        " border-radius:10px; padding:0;"
    )
    vbox = QVBoxLayout(w)
    vbox.setContentsMargins(16, 14, 16, 14)
    vbox.setSpacing(8)
    if title:
        t = QLabel(title)
        t.setStyleSheet("color:#4caf50; font-size:12px; font-weight:600;")
        vbox.addWidget(t)
    for i, step in enumerate(steps, 1):
        row = QHBoxLayout()
        row.setSpacing(10)
        num = QLabel(str(i))
        num.setFixedSize(22, 22)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet(
            "background:#2a5a2a; color:#4caf50; border-radius:11px;"
            " font-size:11px; font-weight:700;"
        )
        lbl = QLabel(step)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setStyleSheet("color:#cccccc; font-size:12px;")
        row.addWidget(num)
        row.addWidget(lbl, stretch=1)
        vbox.addLayout(row)
    return w


def _warn_card(text: str) -> QLabel:
    return _card(text, "#1e1700", "#ffb30066", "#ffb300")


def _info_card(text: str) -> QLabel:
    return _card(text, "#101820", "#4a9eff66", "#88c8ff")


def _link_btn(text: str, url: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        "QPushButton{background:transparent;color:#4a9eff;"
        "border:1px solid #4a9eff55;border-radius:7px;"
        "font-size:12px;padding:6px 16px;}"
        "QPushButton:hover{background:#4a9eff15;border-color:#4a9eff;}"
    )
    btn.clicked.connect(lambda: webbrowser.open(url))
    return btn


# ── Поток скачивания ──────────────────────────────────────────────────────────

class DownloadThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, url: str, dest: str):
        super().__init__()
        self.url  = url
        self.dest = dest

    def run(self):
        try:
            r = requests.get(self.url, stream=True, timeout=180)
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


# ── QThread для фоновой проверки ─────────────────────────────────────────────

class UpdateCheckerThread(QThread):
    update_found = pyqtSignal(str, str, str, str, str, bool)

    def run(self):
        try:
            import time; time.sleep(2)
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
            self.update_found.emit(
                __version__, latest_tag, changelog,
                download_url, asset_name, is_portable
            )
        except Exception:
            pass


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
        self._plat        = _platform()

        self.setWindowTitle(f"{APP_NAME} — Доступно обновление")
        self.setFixedWidth(520)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet("""
            QDialog  { background: #141414; color: #e0e0e0; }
            QLabel   { color: #e0e0e0; }
            QScrollArea { border: none; background: transparent; }
            QWidget#scroll_content { background: transparent; }
        """)
        self._build_ui(current, latest, changelog)

    def _build_ui(self, current, latest, changelog):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Скроллируемая зона ────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget(); content.setObjectName("scroll_content")
        layout = QVBoxLayout(content)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 24, 28, 8)
        scroll.setWidget(content)
        root.addWidget(scroll)

        # Иконка + заголовок
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

        # Платформа-бейдж
        plat_lbl = QLabel(f"🖥 Платформа: <b>{_platform_label()}</b>")
        plat_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plat_lbl.setTextFormat(Qt.TextFormat.RichText)
        plat_lbl.setStyleSheet(
            "color:#88c8ff; font-size:11px;"
            " background:#101820; border-radius:5px; padding:4px 10px;"
        )
        layout.addWidget(plat_lbl)

        # ── Платформо-зависимые предупреждения ────────────────────────────
        if self._plat == "win":
            if self.is_portable:
                layout.addWidget(_card(
                    "✅ <b>Портативная версия</b> — установка без прав администратора.<br>"
                    "Приложение обновится автоматически после скачивания.",
                    "#0d2a0d", "#4caf5044", "#4caf50"
                ))
            else:
                layout.addWidget(_warn_card(
                    "ℹ️ <b>Полный установщик</b> — Windows запросит подтверждение UAC.<br>"
                    "Нажмите «Да» когда появится запрос."
                ))

        elif self._plat in ("mac_arm", "mac_x64"):
            layout.addWidget(_warn_card(
                "⚠️ <b>macOS требует ручной установки</b><br>"
                "Apple не разрешает автоматическую замену приложений без подписи кода.<br>"
                "После скачивания следуйте инструкции ниже."
            ))
            layout.addWidget(_step_card([
                "Нажмите <b>«Скачать»</b> — файл скачается и папка откроется в Finder",
                "Перетащите <b>LessonRecorder.app</b> в папку <b>Программы (Applications)</b>",
                "При появлении запроса — нажмите <b>«Заменить»</b>",
                "Запустите приложение. Если macOS блокирует — нажмите <b>ПКМ → Открыть</b>",
                "Или выполните в Терминале:<br>"
                "<code style='background:#1a1a1a;padding:1px 6px;border-radius:3px;'>"
                "xattr -cr /Applications/LessonRecorder.app</code>",
            ], "📋 Инструкция по обновлению"))

            if self._plat == "mac_arm":
                layout.addWidget(_info_card(
                    "🍎 <b>Apple Silicon (M1/M2/M3/M4)</b><br>"
                    "Скачивается версия для arm64. Убедитесь что устанавливаете "
                    "<b>arm64</b>-сборку, а не x64."
                ))
            else:
                layout.addWidget(_info_card(
                    "💻 <b>Intel Mac</b><br>"
                    "Скачивается версия для x86_64."
                ))

        elif self._plat == "linux":
            layout.addWidget(_info_card(
                "🐧 <b>Linux — ручная установка</b><br>"
                "После скачивания следуйте инструкции."
            ))
            layout.addWidget(_step_card([
                "Нажмите <b>«Скачать»</b> — папка откроется автоматически",
                "Для <b>AppImage</b>: сделайте файл исполняемым:<br>"
                "<code style='background:#1a1a1a;padding:1px 6px;border-radius:3px;'>"
                "chmod +x LessonRecorder*.AppImage</code>",
                "Запустите AppImage двойным кликом или через терминал",
                "Для <b>tar.gz</b>: распакуйте и замените старую версию",
            ], "📋 Инструкция по обновлению"))

        # ── Changelog ────────────────────────────────────────────────────
        if changelog:
            sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color: #2a2a2a;")
            layout.addWidget(sep)

            ch_title = QLabel("Что нового:")
            ch_title.setStyleSheet("color:#888; font-size:11px; font-weight:600;")
            layout.addWidget(ch_title)

            notes = QLabel(changelog[:600] + ("…" if len(changelog) > 600 else ""))
            notes.setWordWrap(True)
            notes.setStyleSheet(
                "background:#111; border-radius:8px; padding:12px;"
                " color:#aaa; font-size:11px;"
            )
            layout.addWidget(notes)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar        { border:none; background:#2a2a2a; border-radius:4px; }
            QProgressBar::chunk { background: qlineargradient(
                x1:0,y1:0,x2:1,y2:0,stop:0 #4a9eff,stop:1 #bc8cff);
                border-radius:4px; }
        """)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color:#888; font-size:12px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addSpacing(4)

        # ── Кнопки ───────────────────────────────────────────────────────
        bottom = QWidget()
        bottom.setStyleSheet(
            "background:#1a1a1a; border-top:1px solid #2a2a2a;"
        )
        btn_row = QHBoxLayout(bottom)
        btn_row.setContentsMargins(28, 14, 28, 14)
        btn_row.setSpacing(12)

        self.skip_btn = QPushButton("Пропустить")
        self.skip_btn.setStyleSheet("""
            QPushButton { background:#2a2a2a; color:#888;
                border:1px solid #3a3a3a; border-radius:8px; padding:9px 20px; }
            QPushButton:hover { background:#333; color:#ccc; }
        """)
        self.skip_btn.clicked.connect(self.reject)

        dl_label = "⬇  Скачать" if self._plat != "win" else "⬇  Скачать и установить"
        self.update_btn = QPushButton(dl_label)
        self.update_btn.setStyleSheet("""
            QPushButton { background:#4a9eff; color:white;
                border:none; border-radius:8px;
                padding:9px 20px; font-weight:bold; }
            QPushButton:hover    { background:#5aadff; }
            QPushButton:disabled { background:#1a3a5a; color:#555; }
        """)
        self.update_btn.clicked.connect(self._start_download)

        btn_row.addWidget(self.skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.update_btn)
        root.addWidget(bottom)

    # ── Скачивание ───────────────────────────────────────────────────────────

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

    def _on_downloaded(self, file_path: str):
        if self._plat == "win":
            self._install_windows(file_path)
        else:
            self._install_unix(file_path)

    # ── Windows ──────────────────────────────────────────────────────────────

    def _install_windows(self, new_exe: str):
        cur_exe = sys.executable
        tmp_bat = os.path.join(tempfile.gettempdir(), "lr_update.bat")

        if self.is_portable:
            bat = (
                "@echo off\r\n"
                "timeout /t 6 /nobreak > nul\r\n"
                f'copy /Y "{new_exe}" "{cur_exe}" > nul\r\n'
                f'start "" "{cur_exe}"\r\n'
            )
        else:
            bat = (
                "@echo off\r\n"
                "timeout /t 6 /nobreak > nul\r\n"
                f'"{new_exe}" /SILENT /RESTARTAPPLICATIONS\r\n'
            )

        with open(tmp_bat, "w", encoding="cp1251") as f:
            f.write(bat)

        subprocess.Popen(
            ["cmd.exe", "/c", "start", "/min", "", "cmd.exe", "/c", tmp_bat],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        self._start_countdown()

    # ── macOS / Linux ────────────────────────────────────────────────────────

    def _install_unix(self, file_path: str):
        import zipfile, shutil as _sh

        folder = os.path.dirname(file_path)

        # Для .zip — распаковываем рядом
        if file_path.endswith(".zip"):
            try:
                extract_dir = os.path.join(folder, "LessonRecorder_update")
                if os.path.exists(extract_dir):
                    _sh.rmtree(extract_dir)
                with zipfile.ZipFile(file_path, "r") as z:
                    z.extractall(extract_dir)
                folder = extract_dir

                # Приложение не подписано сертификатом Apple Developer — macOS
                # может отказаться его открывать ("повреждено") после переноса
                # в Applications. Снимаем карантин сразу здесь, чтобы пользователю
                # не пришлось делать это вручную в Терминале (см. README/диалог).
                if sys.platform == "darwin":
                    for name in os.listdir(extract_dir):
                        if name.endswith(".app"):
                            subprocess.run(
                                ["xattr", "-cr", os.path.join(extract_dir, name)],
                                check=False,
                            )
            except Exception:
                pass  # откроем папку с zip

        # Для AppImage — сделать исполняемым
        if file_path.endswith(".AppImage"):
            try:
                os.chmod(file_path, 0o755)
            except Exception:
                pass

        # Открываем папку в Finder / файловом менеджере
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

        self.progress_bar.setValue(100)

        if sys.platform == "darwin":
            self.status_label.setText(
                "✅ Скачано и распаковано! Finder открыт.\n"
                "Перетащите LessonRecorder.app в папку Программы."
            )
        else:
            self.status_label.setText(
                "✅ Скачано! Папка открыта.\n"
                "Следуйте инструкции выше для установки."
            )

        self.status_label.setStyleSheet("color:#4caf50; font-size:12px;")
        self.skip_btn.setEnabled(True)
        self.skip_btn.setText("Закрыть")

    # ── Обратный отсчёт (Windows) ────────────────────────────────────────────

    def _start_countdown(self):
        self.skip_btn.setEnabled(False)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick)
        self._countdown_timer.start()
        self._tick()

    def _tick(self):
        if self._countdown > 0:
            if self.is_portable:
                msg = f"✅ Скачано! Закрываю через {self._countdown}с — обновление применится автоматически"
            else:
                msg = f"✅ Скачано! Закрываю через {self._countdown}с — установщик запустится автоматически"
            self.status_label.setText(msg)
            self.status_label.setStyleSheet("color:#4caf50; font-size:12px;")
            self._countdown -= 1
        else:
            self._countdown_timer.stop()
            os._exit(0)

    def _on_error(self, msg: str):
        self.status_label.setText(f"❌ {msg}")
        self.status_label.setStyleSheet("color:#f44336; font-size:12px;")
        self.update_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.progress_bar.setVisible(False)


# ── Публичный API ─────────────────────────────────────────────────────────────

def check_for_updates(parent=None):
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
        current=__version__, latest=latest_tag, changelog=changelog,
        download_url=download_url, asset_name=asset_name,
        is_portable=is_portable, parent=parent,
    )
    dlg.exec()


def check_for_updates_async(parent=None):
    checker = UpdateCheckerThread(parent)

    def _show(current, latest, changelog, download_url, asset_name, is_portable):
        dlg = UpdateDialog(
            current=current, latest=latest, changelog=changelog,
            download_url=download_url, asset_name=asset_name,
            is_portable=is_portable, parent=parent,
        )
        dlg.exec()

    checker.update_found.connect(_show)
    checker.start()
    if parent is not None:
        parent._update_checker = checker