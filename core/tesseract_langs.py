"""
Управление Tesseract OCR и языковыми пакетами.

Новые возможности:
  - Скачивание и установка Tesseract прямо из приложения
  - Удаление отдельных языковых пакетов
  - Увеличенный интерфейс с вкладками

Языки ищутся в:
  1. Рядом с tesseract.exe (динамически)
  2. ~/.lesson_recorder/tessdata/
  3. Стандартные пути Windows
"""
import os
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QScrollArea, QWidget, QGridLayout, QCheckBox,
    QFrame, QTabWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

USER_TESSDATA     = Path.home() / ".lesson_recorder" / "tessdata"
TESSDATA_BASE_URL = "https://github.com/tesseract-ocr/tessdata/raw/main"
_SKIP_STEMS       = {"snum", "pdf", "configs", "tessconfigs", "osd", ""}

TESSERACT_INSTALLER_URL = (
    "https://digi.bib.uni-mannheim.de/tesseract/"
    "tesseract-ocr-w64-setup-5.4.0.20240606.exe"
)
TESSERACT_INSTALLER_VERSION = "5.4.0"

LANG_NAMES: dict[str, str] = {
    "rus": "Русский",    "eng": "English",       "deu": "Deutsch",
    "fra": "Français",   "spa": "Español",        "ita": "Italiano",
    "por": "Português",  "pol": "Polski",          "nld": "Nederlands",
    "swe": "Svenska",    "nor": "Norsk",           "dan": "Dansk",
    "fin": "Suomi",      "tur": "Türkçe",          "ukr": "Українська",
    "bel": "Беларуская", "bul": "Български",       "ces": "Čeština",
    "slk": "Slovenčina", "hun": "Magyar",           "ron": "Română",
    "hrv": "Hrvatski",   "srp": "Српски",           "ara": "العربية",
    "heb": "עברית",      "jpn": "日本語",           "chi_sim": "中文简体",
    "chi_tra": "中文繁體","kor": "한국어",            "hin": "हिन्दी",
    "tha": "ภาษาไทย",    "vie": "Tiếng Việt",      "ind": "Bahasa Indonesia",
    "kat": "ქართული",    "ell": "Ελληνικά",        "lav": "Latviešu",
    "lit": "Lietuvių",   "est": "Eesti",           "equ": "Формулы/Math",
}
DOWNLOADABLE_LANGS = list(LANG_NAMES.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Утилиты поиска
# ─────────────────────────────────────────────────────────────────────────────

_tesseract_cmd_cache: str | None | bool = False   # False = не проверялось


def find_tesseract_cmd() -> str | None:
    """
    Ищет tesseract.exe быстрыми методами (без rglob по всему диску).
    Результат кешируется на время сессии.
    """
    global _tesseract_cmd_cache
    if _tesseract_cmd_cache is not False:
        return _tesseract_cmd_cache   # type: ignore[return-value]

    result = _find_tesseract_cmd_uncached()
    _tesseract_cmd_cache = result
    return result


def _find_tesseract_cmd_uncached() -> str | None:
    # 1. Фиксированные пути — мгновенно
    for p in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Tesseract-OCR\tesseract.exe",
        r"C:\Tesseract\tesseract.exe",
        r"C:\tools\Tesseract-OCR\tesseract.exe",
    ]:
        if Path(p).exists():
            return p

    # 2. PATH — мгновенно
    found = shutil.which("tesseract")
    if found:
        return found

    # 3. Реестр Windows — быстро
    try:
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for sub in [r"SOFTWARE\Tesseract-OCR",
                        r"SOFTWARE\WOW6432Node\Tesseract-OCR"]:
                try:
                    with winreg.OpenKey(hive, sub) as key:
                        install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                        exe = Path(install_dir) / "tesseract.exe"
                        if exe.exists():
                            return str(exe)
                except (FileNotFoundError, OSError):
                    pass
    except ImportError:
        pass

    # 4. Команда where (Windows) / which (Unix) — быстро
    import subprocess
    try:
        r = subprocess.run(
            ["where", "tesseract"] if sys.platform == "win32" else ["which", "tesseract"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0:
            line = r.stdout.strip().splitlines()[0].strip()
            if line and Path(line).exists():
                return line
    except Exception:
        pass

    # НЕ используем rglob — это сканирование всего диска (десятки секунд)
    return None


def get_all_tessdata_dirs() -> list[Path]:
    dirs: list[Path] = []
    cmd = find_tesseract_cmd()
    if cmd:
        d = Path(cmd).parent / "tessdata"
        if d.exists():
            dirs.append(d)
    if USER_TESSDATA.exists():
        dirs.append(USER_TESSDATA)
    for p in [r"C:\Program Files\Tesseract-OCR\tessdata",
              r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
              r"C:\Tesseract-OCR\tessdata"]:
        pp = Path(p)
        if pp.exists() and pp not in dirs:
            dirs.append(pp)
    return dirs


def setup_tesseract() -> bool:
    cmd = find_tesseract_cmd()
    if not cmd:
        return False
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = cmd
        if USER_TESSDATA.exists() and any(USER_TESSDATA.glob("*.traineddata")):
            os.environ["TESSDATA_PREFIX"] = str(USER_TESSDATA)
        else:
            exe_td = Path(cmd).parent / "tessdata"
            if exe_td.exists():
                os.environ["TESSDATA_PREFIX"] = str(exe_td)
        return True
    except ImportError:
        return False


def ensure_user_tessdata() -> Path:
    USER_TESSDATA.mkdir(parents=True, exist_ok=True)
    return USER_TESSDATA


def get_lang_file(code: str, tessdata_dir: Path) -> Path:
    return tessdata_dir / f"{code}.traineddata"


def is_lang_available(code: str) -> bool:
    return any(get_lang_file(code, d).exists() for d in get_all_tessdata_dirs())


def get_available_langs() -> list[str]:
    langs: set[str] = set()
    for d in get_all_tessdata_dirs():
        for f in d.glob("*.traineddata"):
            if f.stem not in _SKIP_STEMS:
                langs.add(f.stem)
    return sorted(langs)


def delete_lang(code: str) -> bool:
    """Удаляет языковой пакет из пользовательской tessdata папки."""
    path = get_lang_file(code, USER_TESSDATA)
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError:
            return False
    return False


def mirror_system_langs_to_user() -> int:
    ensure_user_tessdata()
    count = 0
    for d in get_all_tessdata_dirs():
        if d == USER_TESSDATA:
            continue
        for f in d.glob("*.traineddata"):
            dest = USER_TESSDATA / f.name
            if not dest.exists():
                try:
                    shutil.copy2(f, dest)
                    count += 1
                except OSError:
                    pass
    return count


def prepare_tessdata_for_ocr(lang_codes: list[str]) -> tuple[str, str]:
    ensure_user_tessdata()
    mirror_system_langs_to_user()

    available = [c for c in lang_codes if get_lang_file(c, USER_TESSDATA).exists()]
    if not available:
        for code in lang_codes:
            for d in get_all_tessdata_dirs():
                if get_lang_file(code, d).exists():
                    available.append(code)
                    break

    if not available:
        for d in get_all_tessdata_dirs():
            if get_lang_file("eng", d).exists():
                os.environ["TESSDATA_PREFIX"] = str(d)
                return "eng", str(d)
        return "eng", ""

    tessdata_dir = str(USER_TESSDATA)
    if not any(get_lang_file(c, USER_TESSDATA).exists() for c in available):
        for d in get_all_tessdata_dirs():
            if any(get_lang_file(c, d).exists() for c in available):
                tessdata_dir = str(d)
                break

    os.environ["TESSDATA_PREFIX"] = tessdata_dir
    return "+".join(available), tessdata_dir


# ─────────────────────────────────────────────────────────────────────────────
# Общие стили
# ─────────────────────────────────────────────────────────────────────────────

def _btn_style(bg: str, fg: str = "#fff") -> str:
    return (
        f"QPushButton{{background:{bg};color:{fg};border:none;"
        f"border-radius:8px;padding:9px 24px;font-size:13px;font-weight:600;}}"
        f"QPushButton:hover{{background:{bg}cc;}}"
        f"QPushButton:disabled{{background:#252525;color:#555;}}"
    )

_BTN_OUTLINE = (
    "QPushButton{background:transparent;color:#888;border:1px solid #3a3a3a;"
    "border-radius:8px;padding:9px 24px;font-size:13px;}"
    "QPushButton:hover{background:#252525;color:#ccc;}"
)


# ─────────────────────────────────────────────────────────────────────────────
# Потоки
# ─────────────────────────────────────────────────────────────────────────────

class LangDownloadThread(QThread):
    lang_started  = pyqtSignal(str)
    lang_progress = pyqtSignal(str, int)
    lang_done     = pyqtSignal(str)
    lang_error    = pyqtSignal(str, str)
    all_done      = pyqtSignal()

    def __init__(self, lang_codes: list[str]):
        super().__init__()
        self.lang_codes = lang_codes
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import requests
        ensure_user_tessdata()
        for code in self.lang_codes:
            if self._cancelled:
                break
            dest = get_lang_file(code, USER_TESSDATA)
            if dest.exists():
                self.lang_done.emit(code)
                continue
            self.lang_started.emit(code)
            for d in get_all_tessdata_dirs():
                src = get_lang_file(code, d)
                if src.exists():
                    try:
                        shutil.copy2(src, dest)
                        self.lang_done.emit(code)
                    except OSError as e:
                        self.lang_error.emit(code, str(e))
                    break
            else:
                url = f"{TESSDATA_BASE_URL}/{code}.traineddata"
                tmp = dest.with_suffix(".tmp")
                try:
                    r = requests.get(url, stream=True, timeout=90)
                    r.raise_for_status()
                    total = int(r.headers.get("content-length", 0))
                    downloaded = 0
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            if self._cancelled:
                                break
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total:
                                    self.lang_progress.emit(
                                        code, int(downloaded / total * 100)
                                    )
                    if self._cancelled:
                        tmp.unlink(missing_ok=True)
                        break
                    tmp.rename(dest)
                    self.lang_done.emit(code)
                except Exception as e:
                    tmp.unlink(missing_ok=True)
                    self.lang_error.emit(code, str(e))
        self.all_done.emit()


class TesseractInstallerThread(QThread):
    progress = pyqtSignal(int)
    status   = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import requests
        try:
            self.status.emit("Подключаюсь к серверу…")
            tmp_dir = tempfile.mkdtemp(prefix="lr_tess_")
            dest    = Path(tmp_dir) / "tesseract-installer.exe"
            tmp     = dest.with_suffix(".tmp")

            r = requests.get(TESSERACT_INSTALLER_URL, stream=True, timeout=30)
            r.raise_for_status()
            total      = int(r.headers.get("content-length", 0))
            downloaded = 0

            self.status.emit(f"Скачиваю Tesseract {TESSERACT_INSTALLER_VERSION}…")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if self._cancelled:
                        tmp.unlink(missing_ok=True)
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(int(downloaded / total * 100))

            tmp.rename(dest)
            self.status.emit("Загрузка завершена — запускаю установщик…")
            self.finished.emit(str(dest))
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Вкладка: Tesseract
# ─────────────────────────────────────────────────────────────────────────────

class TesseractTab(QWidget):
    installed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: TesseractInstallerThread | None = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(32, 32, 32, 32)

        # Статус-карточка
        cmd = find_tesseract_cmd()
        if cmd:
            bg, border, icon = "#0a2010", "#4caf5044", "✅"
            msg = f"Tesseract найден:\n{cmd}"
            msg_color = "#4caf50"
        else:
            bg, border, icon = "#1e1400", "#ffb30044", "⚠️"
            msg = "Tesseract не найден на этом компьютере"
            msg_color = "#ffb300"

        card = QWidget()
        card.setStyleSheet(
            f"background:{bg}; border:1px solid {border}; border-radius:12px;"
        )
        card_row = QHBoxLayout(card)
        card_row.setContentsMargins(24, 20, 24, 20)
        card_row.setSpacing(16)
        ic = QLabel(icon)
        ic.setStyleSheet("font-size:32px;")
        card_row.addWidget(ic)
        msg_lbl = QLabel(msg)
        msg_lbl.setStyleSheet(f"color:{msg_color}; font-size:14px;")
        msg_lbl.setWordWrap(True)
        card_row.addWidget(msg_lbl, stretch=1)
        layout.addWidget(card)

        # Описание
        desc = QLabel(
            "<b>Tesseract OCR</b> — бесплатный движок распознавания текста (Google).<br>"
            "Без него функция «Фото → Текст» не работает.<br><br>"
            f"Будет скачан установщик <b>v{TESSERACT_INSTALLER_VERSION}</b> (~48 МБ) "
            "с официального репозитория <b>UB-Mannheim</b>."
        )
        desc.setStyleSheet("color:#aaa; font-size:13px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Прогресс
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setFixedHeight(22)
        self.pbar.setVisible(False)
        self.pbar.setFormat("%p%")
        self.pbar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pbar.setStyleSheet(
            "QProgressBar{border:none;background:#21262d;border-radius:11px;"
            "color:#e6edf3;font-size:11px;font-weight:600;}"
            "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #58a6ff,stop:1 #bc8cff);border-radius:11px;}"
        )
        layout.addWidget(self.pbar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#888; font-size:12px;")
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.dl_btn = QPushButton("⬇  Скачать и установить Tesseract")
        self.dl_btn.setFixedHeight(46)
        self.dl_btn.setStyleSheet(_btn_style("#2a5298"))
        self.dl_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.dl_btn)

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setFixedHeight(46)
        self.cancel_btn.setStyleSheet(_BTN_OUTLINE)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        note = QLabel(
            "💡 При установке рекомендуется отметить <b>«Additional language data»</b> — "
            "тогда языки скачивать отдельно не нужно."
        )
        note.setStyleSheet(
            "color:#888; font-size:12px; background:#1c1c1c;"
            " border-radius:8px; padding:10px 14px;"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()

    def _start_download(self):
        self.dl_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.pbar.setVisible(True)
        self.pbar.setValue(0)
        self._thread = TesseractInstallerThread()
        self._thread.progress.connect(self.pbar.setValue)
        self._thread.status.connect(self.status_lbl.setText)
        self._thread.finished.connect(self._on_downloaded)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_downloaded(self, exe_path: str):
        self.pbar.setValue(100)
        self.cancel_btn.setVisible(False)
        try:
            subprocess.Popen([exe_path], shell=True)
            self.status_lbl.setText(
                "✅ Установщик запущен. После установки перезапусти приложение."
            )
            # Сбрасываем кеш — после установки tesseract будет доступен
            global _tesseract_cmd_cache
            _tesseract_cmd_cache = False
            self.installed.emit()
        except Exception as e:
            self.status_lbl.setText(f"❌ Не удалось запустить: {e}")
        self.dl_btn.setEnabled(True)

    def _on_error(self, msg: str):
        self.status_lbl.setText(f"❌ {msg}")
        self.pbar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.dl_btn.setEnabled(True)

    def _cancel(self):
        if self._thread:
            self._thread.cancel()
        self.cancel_btn.setVisible(False)
        self.dl_btn.setEnabled(True)
        self.pbar.setVisible(False)
        self.status_lbl.setText("Отменено.")


# ─────────────────────────────────────────────────────────────────────────────
# Вкладка: Языки
# ─────────────────────────────────────────────────────────────────────────────

class LangsTab(QWidget):
    langs_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: LangDownloadThread | None = None
        self._checkboxes:  dict[str, QCheckBox] = {}
        self._row_widgets: dict[str, QWidget]   = {}
        self._available  = set(get_available_langs())
        self._user_langs = self._scan_user_langs()
        self._grid_layout: QGridLayout | None = None
        self._grid_container: QWidget | None  = None
        self._build()

    def _scan_user_langs(self) -> set[str]:
        if not USER_TESSDATA.exists():
            return set()
        return {
            f.stem for f in USER_TESSDATA.glob("*.traineddata")
            if f.stem not in _SKIP_STEMS
        }

    def refresh(self):
        self._available  = set(get_available_langs())
        self._user_langs = self._scan_user_langs()
        self._rebuild_grid()

    # ── строим UI ────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(32, 24, 32, 24)

        # Инфо о tessdata
        dirs = get_all_tessdata_dirs()
        if dirs:
            info_txt = "📁 tessdata: " + "  ·  ".join(str(d) for d in dirs[:2])
        else:
            info_txt = "⚠️ tessdata не найдена. Сначала установи Tesseract (вкладка «Tesseract»)."
        info = QLabel(info_txt)
        info.setStyleSheet(
            "color:#4a9eff; font-size:12px; background:#131d2a;"
            " border-radius:6px; padding:8px 12px;"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Быстрый выбор
        qrow = QHBoxLayout()
        qrow.setSpacing(8)
        for cap, codes in [
            ("🇷🇺 Рус+Eng",  ["rus", "eng"]),
            ("🇪🇺 Европа",   ["rus","eng","deu","fra","spa","ita","por","pol","ukr"]),
            ("Все",           DOWNLOADABLE_LANGS),
            ("Снять всё",     []),
        ]:
            b = QPushButton(cap)
            b.setFixedHeight(32)
            b.setStyleSheet(
                "QPushButton{background:#202020;color:#aaa;border:1px solid #333;"
                "border-radius:7px;padding:0 16px;font-size:12px;}"
                "QPushButton:hover{background:#2a2a2a;color:#fff;}"
            )
            _codes = list(codes)
            b.clicked.connect(lambda _, c=_codes: self._quick(c))
            qrow.addWidget(b)
        qrow.addStretch()
        layout.addLayout(qrow)

        # Сетка
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{border:1px solid #252525;border-radius:10px;background:#0e0e0e;}"
            "QScrollBar:vertical{background:#1a1a1a;width:8px;border-radius:4px;}"
            "QScrollBar::handle:vertical{background:#333;border-radius:4px;min-height:30px;}"
        )
        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background:transparent;")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(16, 16, 16, 16)
        self._grid_layout.setHorizontalSpacing(12)
        self._grid_layout.setVerticalSpacing(4)
        self._rebuild_grid()
        scroll.setWidget(self._grid_container)
        layout.addWidget(scroll)

        # Прогресс
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setFixedHeight(22)
        self.pbar.setVisible(False)
        self.pbar.setFormat("%p%")
        self.pbar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pbar.setStyleSheet(
            "QProgressBar{border:none;background:#21262d;border-radius:11px;"
            "color:#e6edf3;font-size:11px;font-weight:600;}"
            "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #58a6ff,stop:1 #bc8cff);border-radius:11px;}"
        )
        layout.addWidget(self.pbar)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#888; font-size:12px;")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        # Кнопка установки
        brow = QHBoxLayout()
        self.install_btn = QPushButton("⬇  Установить выбранные")
        self.install_btn.setFixedHeight(44)
        self.install_btn.setMinimumWidth(240)
        self.install_btn.setStyleSheet(_btn_style("#27ae60"))
        self.install_btn.clicked.connect(self._start_install)
        brow.addWidget(self.install_btn)
        brow.addStretch()
        layout.addLayout(brow)

    def _rebuild_grid(self):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checkboxes.clear()
        self._row_widgets.clear()

        COLS = 2
        for idx, code in enumerate(DOWNLOADABLE_LANGS):
            is_installed = code in self._available
            is_user      = code in self._user_langs

            row_w = QWidget()
            row_w.setStyleSheet(
                "background:#161616; border-radius:7px;" if is_installed
                else "background:transparent;"
            )
            row_layout = QHBoxLayout(row_w)
            row_layout.setContentsMargins(10, 5, 10, 5)
            row_layout.setSpacing(8)

            name = LANG_NAMES.get(code, code)
            cb = QCheckBox(f"{name}  [{code}]")
            cb.setEnabled(not is_installed)
            cb.setStyleSheet(
                f"QCheckBox{{color:{'#555' if is_installed else '#d8d8d8'};"
                "font-size:13px;background:transparent;}}"
                "QCheckBox::indicator{width:16px;height:16px;}"
                "QCheckBox::indicator:unchecked{background:#252525;border:1px solid #444;border-radius:4px;}"
                "QCheckBox::indicator:checked{background:#4a9eff;border:1px solid #4a9eff;border-radius:4px;}"
                "QCheckBox::indicator:disabled{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:4px;}"
            )
            self._checkboxes[code] = cb
            row_layout.addWidget(cb, stretch=1)

            if is_installed:
                badge = QLabel("✅")
                badge.setStyleSheet(
                    "color:#4caf50; font-size:12px; background:transparent;"
                )
                row_layout.addWidget(badge)

                if is_user:
                    del_btn = QPushButton("🗑")
                    del_btn.setFixedSize(30, 30)
                    del_btn.setToolTip(f"Удалить {name}")
                    del_btn.setStyleSheet(
                        "QPushButton{background:#3a1a1a;color:#f44336;border:none;"
                        "border-radius:6px;font-size:14px;}"
                        "QPushButton:hover{background:#5a2020;}"
                    )
                    del_btn.clicked.connect(lambda _, c=code: self._delete_lang(c))
                    row_layout.addWidget(del_btn)
                else:
                    sys_badge = QLabel("sys")
                    sys_badge.setStyleSheet(
                        "color:#555; font-size:10px; background:#1e1e1e;"
                        " border-radius:4px; padding:2px 6px;"
                    )
                    sys_badge.setToolTip("Системный пакет — удалить через деинсталляцию Tesseract")
                    row_layout.addWidget(sys_badge)
            else:
                placeholder = QLabel()
                placeholder.setFixedWidth(50)
                row_layout.addWidget(placeholder)

            self._row_widgets[code] = row_w
            grid_row = idx // COLS
            grid_col = idx % COLS
            self._grid_layout.addWidget(row_w, grid_row, grid_col)

    # ── операции ─────────────────────────────────────────────────────────

    def _quick(self, codes: list):
        for code, cb in self._checkboxes.items():
            if cb.isEnabled():
                cb.setChecked(code in codes)

    def _delete_lang(self, code: str):
        name = LANG_NAMES.get(code, code)
        if delete_lang(code):
            self.status.setText(f"🗑 Удалён: {name} [{code}]")
            self._available.discard(code)
            self._user_langs.discard(code)
            self._rebuild_grid()
            self.langs_changed.emit()
        else:
            self.status.setText(
                f"❌ Не удалось удалить [{code}] — файл не в пользовательской папке"
            )

    def _start_install(self):
        to_do = [c for c, cb in self._checkboxes.items()
                 if cb.isChecked() and cb.isEnabled()]
        if not to_do:
            self.status.setText("⚠️ Ничего не выбрано.")
            return
        self.install_btn.setEnabled(False)
        self.pbar.setVisible(True)
        self.pbar.setValue(0)
        self.status.setText(f"⬇ Начинаю скачивать {len(to_do)} языков…")
        self._thread = LangDownloadThread(to_do)
        self._thread.lang_started.connect(
            lambda c: self.status.setText(
                f"⬇ {LANG_NAMES.get(c, c)} [{c}]…"
            )
        )
        self._thread.lang_progress.connect(
            lambda c, p: (
                self.pbar.setValue(p),
                self.status.setText(f"⬇ {LANG_NAMES.get(c, c)} [{c}]… {p}%"),
            )
        )
        self._thread.lang_done.connect(self._on_lang_done)
        self._thread.lang_error.connect(
            lambda c, e: self.status.setText(f"❌ {LANG_NAMES.get(c, c)}: {e}")
        )
        self._thread.all_done.connect(self._on_all_done)
        self._thread.start()

    def _on_lang_done(self, code: str):
        self._available.add(code)
        self._user_langs.add(code)
        self.langs_changed.emit()

    def _on_all_done(self):
        self.install_btn.setEnabled(True)
        self.pbar.setVisible(False)
        self.status.setText("✅ Все выбранные языки установлены!")
        self._rebuild_grid()

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._thread.cancel()
            self._thread.wait(2000)
        super().closeEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Главный диалог
# ─────────────────────────────────────────────────────────────────────────────

class LangInstallDialog(QDialog):
    langs_changed = pyqtSignal()

    def __init__(self, preselect: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tesseract OCR — Управление")
        self.setMinimumSize(860, 680)
        self.resize(920, 740)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet("""
            QDialog {
                background: #111111;
                color: #e0e0e0;
            }
            QTabWidget::pane {
                border: 1px solid #252525;
                border-top: none;
                border-radius: 0 0 10px 10px;
                background: #111111;
            }
            QTabBar {
                background: transparent;
            }
            QTabBar::tab {
                background: #191919;
                color: #777;
                border: 1px solid #252525;
                border-bottom: none;
                border-radius: 9px 9px 0 0;
                padding: 11px 32px;
                font-size: 13px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #111111;
                color: #e0e0e0;
                border-bottom: 1px solid #111111;
            }
            QTabBar::tab:hover:!selected {
                background: #202020;
                color: #bbb;
            }
            QLabel { background: transparent; color: #e0e0e0; }
            QScrollBar:vertical {
                background: #1a1a1a; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #353535; border-radius: 4px; min-height: 30px;
            }
        """)
        self._preselect = list(preselect or [])
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Заголовок ────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet("background:#181818; border-bottom:1px solid #252525;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(32, 0, 32, 0)
        title = QLabel("⚙️  Tesseract OCR")
        title.setStyleSheet("font-size:18px; font-weight:700; color:#e0e0e0;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        sub = QLabel("Установка и управление языковыми пакетами")
        sub.setStyleSheet("color:#555; font-size:12px;")
        h_layout.addWidget(sub)
        layout.addWidget(header)

        # ── Вкладки ───────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setContentsMargins(0, 0, 0, 0)

        self._tess_tab  = TesseractTab()
        self._langs_tab = LangsTab()

        self._tabs.addTab(self._tess_tab,  "🔧  Tesseract")
        self._tabs.addTab(self._langs_tab, "🌍  Языки OCR")

        # Если Tesseract уже установлен — сразу показываем языки
        if find_tesseract_cmd():
            self._tabs.setCurrentIndex(1)

        self._langs_tab.langs_changed.connect(self.langs_changed)
        self._tess_tab.installed.connect(lambda: self._tabs.setCurrentIndex(1))

        layout.addWidget(self._tabs)

        # ── Подвал ───────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(62)
        footer.setStyleSheet("background:#181818; border-top:1px solid #252525;")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(32, 0, 32, 0)
        f_layout.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.setFixedHeight(38)
        close_btn.setMinimumWidth(120)
        close_btn.setStyleSheet(_BTN_OUTLINE)
        close_btn.clicked.connect(self.accept)
        f_layout.addWidget(close_btn)
        layout.addWidget(footer)

    def closeEvent(self, event):
        self._langs_tab.closeEvent(event)
        super().closeEvent(event)
