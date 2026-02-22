"""
Управление языковыми пакетами Tesseract OCR.

Языки хранятся в двух местах:
  1. Системная tessdata: C:\Program Files\Tesseract-OCR\tessdata\
  2. Пользовательская tessdata: ~/.lesson_recorder/tessdata/

При OCR всегда используется пользовательская папка (TESSDATA_PREFIX).
Системные языки автоматически копируются туда при первом использовании.
Новые языки скачиваются с GitHub.
"""
import os
import shutil
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QScrollArea, QWidget, QGridLayout, QCheckBox,
    QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# ── Пути ──────────────────────────────────────────────────────────────────────

SYSTEM_TESSDATA   = Path(r"C:\Program Files\Tesseract-OCR\tessdata")
USER_TESSDATA     = Path.home() / ".lesson_recorder" / "tessdata"
TESSDATA_BASE_URL = "https://github.com/tesseract-ocr/tessdata/raw/main"

LANG_NAMES: dict[str, str] = {
    "rus": "Русский",
    "eng": "English",
    "deu": "Deutsch",
    "fra": "Français",
    "spa": "Español",
    "ita": "Italiano",
    "por": "Português",
    "pol": "Polski",
    "nld": "Nederlands",
    "swe": "Svenska",
    "nor": "Norsk",
    "dan": "Dansk",
    "fin": "Suomi",
    "tur": "Türkçe",
    "ukr": "Українська",
    "bel": "Беларуская",
    "bul": "Български",
    "ces": "Čeština",
    "slk": "Slovenčina",
    "hun": "Magyar",
    "ron": "Română",
    "hrv": "Hrvatski",
    "srp": "Српски",
    "ara": "العربية",
    "heb": "עברית",
    "jpn": "日本語",
    "chi_sim": "中文简体",
    "chi_tra": "中文繁體",
    "kor": "한국어",
    "hin": "हिन्दी",
    "tha": "ภาษาไทย",
    "vie": "Tiếng Việt",
    "ind": "Bahasa Indonesia",
    "kat": "ქართული",
    "ell": "Ελληνικά",
    "lav": "Latviešu",
    "lit": "Lietuvių",
    "est": "Eesti",
    "equ": "Формулы/Math",
}

DOWNLOADABLE_LANGS = list(LANG_NAMES.keys())
_SKIP_STEMS = {"snum", "pdf", "configs", "tessconfigs", ""}


# ── Поиск Tesseract ───────────────────────────────────────────────────────────

def find_tesseract_cmd() -> str | None:
    """Ищет tesseract.exe: стандартные пути → PATH."""
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\Public\Tesseract-OCR\tesseract.exe",
    ]
    for p in candidates:
        if Path(p).exists():
            return p

    # Ищем в PATH
    import shutil as _shutil
    found = _shutil.which("tesseract")
    if found:
        return found

    return None


def setup_tesseract() -> bool:
    """
    Настраивает pytesseract и TESSDATA_PREFIX.
    Возвращает True если Tesseract найден.
    НЕ импортирует из photo_ocr — нет circular dependency.
    """
    cmd = find_tesseract_cmd()
    if cmd is None:
        return False
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = cmd

        # Устанавливаем TESSDATA_PREFIX на пользовательскую папку
        # чтобы Tesseract видел скачанные языки
        user_td = ensure_user_tessdata()
        os.environ["TESSDATA_PREFIX"] = str(user_td)

        return True
    except ImportError:
        return False


# ── Работа с файлами tessdata ─────────────────────────────────────────────────

def ensure_user_tessdata() -> Path:
    """Создаёт пользовательскую папку tessdata."""
    USER_TESSDATA.mkdir(parents=True, exist_ok=True)
    return USER_TESSDATA


def get_lang_file(code: str, tessdata_dir: Path) -> Path:
    return tessdata_dir / f"{code}.traineddata"


def is_lang_available(code: str) -> bool:
    return (
        get_lang_file(code, USER_TESSDATA).exists() or
        get_lang_file(code, SYSTEM_TESSDATA).exists()
    )


def get_available_langs() -> list[str]:
    """
    Сканирует обе tessdata папки и возвращает список всех доступных языков.
    НЕ использует pytesseract.get_languages() — он видит только системные языки.
    """
    langs: set[str] = set()

    for tessdata in [USER_TESSDATA, SYSTEM_TESSDATA]:
        if tessdata.exists():
            for f in tessdata.glob("*.traineddata"):
                code = f.stem
                if code not in _SKIP_STEMS:
                    langs.add(code)

    return sorted(langs)


def mirror_system_langs_to_user() -> int:
    """
    Копирует все .traineddata из системной tessdata в пользовательскую
    если их там нет. Возвращает количество скопированных файлов.
    """
    if not SYSTEM_TESSDATA.exists():
        return 0
    ensure_user_tessdata()
    count = 0
    for f in SYSTEM_TESSDATA.glob("*.traineddata"):
        dest = USER_TESSDATA / f.name
        if not dest.exists():
            try:
                shutil.copy2(f, dest)
                count += 1
            except OSError:
                pass
    return count


def mirror_system_lang(code: str) -> bool:
    """Копирует один язык из системной tessdata в пользовательскую."""
    user_file = get_lang_file(code, USER_TESSDATA)
    if user_file.exists():
        return True
    sys_file = get_lang_file(code, SYSTEM_TESSDATA)
    if sys_file.exists():
        ensure_user_tessdata()
        try:
            shutil.copy2(sys_file, user_file)
            return True
        except OSError:
            return False
    return False


def prepare_tessdata_for_ocr(lang_codes: list[str]) -> tuple[str, str]:
    """
    Готовит tessdata для OCR:
    1. Синхронизирует все системные языки в USER_TESSDATA (при первом вызове)
    2. Устанавливает TESSDATA_PREFIX = USER_TESSDATA
    3. Возвращает (lang_string, tessdata_dir_str)
    """
    ensure_user_tessdata()

    # При первом вызове — зеркалируем ВСЕ системные языки
    # Это гарантирует что eng, rus и т.п. доступны в USER_TESSDATA
    mirror_system_langs_to_user()

    # Устанавливаем TESSDATA_PREFIX — Tesseract будет искать здесь
    tessdata_dir = str(USER_TESSDATA)
    os.environ["TESSDATA_PREFIX"] = tessdata_dir

    # Фильтруем: только языки которые реально есть в USER_TESSDATA
    available = [
        code for code in lang_codes
        if get_lang_file(code, USER_TESSDATA).exists()
    ]

    if not available:
        # Если ничего нет — пробуем eng как last resort
        eng_file = get_lang_file("eng", USER_TESSDATA)
        if eng_file.exists():
            available = ["eng"]
        else:
            return "eng", tessdata_dir

    return "+".join(available), tessdata_dir


def get_missing_langs(lang_codes: list[str]) -> list[str]:
    return [c for c in lang_codes if not is_lang_available(c)]


# ── Поток скачивания языков ───────────────────────────────────────────────────

class LangDownloadThread(QThread):
    lang_started  = pyqtSignal(str)
    lang_progress = pyqtSignal(str, int)
    lang_done     = pyqtSignal(str)
    lang_error    = pyqtSignal(str, str)
    all_done      = pyqtSignal()

    def __init__(self, lang_codes: list[str]):
        super().__init__()
        self.lang_codes  = lang_codes
        self._cancelled  = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import requests
        ensure_user_tessdata()

        for code in self.lang_codes:
            if self._cancelled:
                break

            # Если уже есть — пропускаем
            dest = get_lang_file(code, USER_TESSDATA)
            if dest.exists():
                self.lang_done.emit(code)
                continue

            # Сначала пробуем скопировать из системной tessdata
            if mirror_system_lang(code):
                self.lang_started.emit(code)
                self.lang_done.emit(code)
                continue

            # Скачиваем с GitHub
            self.lang_started.emit(code)
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
                                self.lang_progress.emit(code, int(downloaded / total * 100))

                if self._cancelled:
                    tmp.unlink(missing_ok=True)
                    break

                tmp.rename(dest)
                self.lang_done.emit(code)

            except Exception as e:
                tmp.unlink(missing_ok=True)
                self.lang_error.emit(code, str(e))

        self.all_done.emit()


# ── Диалог установки языков ───────────────────────────────────────────────────

class LangInstallDialog(QDialog):
    """Диалог скачивания языковых пакетов Tesseract."""
    langs_changed = pyqtSignal()

    def __init__(self, preselect: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Установка языков OCR")
        self.setMinimumSize(560, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("""
            QDialog { background: #1a1a1a; color: #e0e0e0; }
            QLabel  { color: #e0e0e0; }
            QScrollArea { background: transparent; border: none; }
        """)

        self._preselect = set(preselect or [])
        self._checkboxes:   dict[str, QCheckBox] = {}
        self._status_labels: dict[str, QLabel]   = {}
        self._download_thread: LangDownloadThread | None = None
        self._available_now = set(get_available_langs())

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        hdr = QLabel("🌍  Языковые пакеты Tesseract OCR")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(hdr)

        hint = QLabel(
            "✅ — уже установлен  |  отмечай языки для скачивания.\n"
            "Файлы сохраняются в ~/.lesson_recorder/tessdata/  (~20–50 МБ каждый)."
        )
        hint.setStyleSheet("color: #888; font-size: 12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Системная tessdata — если есть, показываем инфо
        if SYSTEM_TESSDATA.exists():
            sys_langs = [f.stem for f in SYSTEM_TESSDATA.glob("*.traineddata")
                         if f.stem not in _SKIP_STEMS]
            if sys_langs:
                sys_info = QLabel(
                    f"ℹ️ Найдена системная Tesseract: {len(sys_langs)} языков. "
                    "Они будут скопированы автоматически при первом OCR."
                )
                sys_info.setStyleSheet(
                    "color: #4a9eff; font-size: 11px;"
                    " background: #1a2a3a; border-radius: 5px; padding: 5px 8px;"
                )
                sys_info.setWordWrap(True)
                layout.addWidget(sys_info)

        # Быстрые кнопки выбора
        quick_row = QHBoxLayout()
        presets = [
            ("🇷🇺 Рус+Eng",      ["rus", "eng"]),
            ("🇪🇺 Европейские",  ["rus", "eng", "deu", "fra", "spa", "ita", "por", "pol", "ukr"]),
            ("Все",               DOWNLOADABLE_LANGS),
            ("Снять",             []),
        ]
        for caption, codes in presets:
            btn = QPushButton(caption)
            btn.setFixedHeight(26)
            btn.setStyleSheet(
                "QPushButton { background:#2a2a2a; color:#aaa; border:1px solid #3a3a3a;"
                " border-radius:5px; padding:0 10px; font-size:11px; }"
                "QPushButton:hover { background:#333; color:#fff; }"
            )
            _c = list(codes)
            btn.clicked.connect(lambda _, c=_c: self._quick_select(c))
            quick_row.addWidget(btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        # Сетка языков
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border:1px solid #2a2a2a; border-radius:8px; background:#111; }"
        )
        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)

        COLS = 2
        for idx, code in enumerate(DOWNLOADABLE_LANGS):
            name      = LANG_NAMES.get(code, code.upper())
            installed = code in self._available_now

            cb = QCheckBox(f"{name}  [{code}]")
            cb.setChecked(code in self._preselect and not installed)
            cb.setEnabled(not installed)
            color = "#555" if installed else "#d0d0d0"
            cb.setStyleSheet(
                f"QCheckBox {{ color:{color}; font-size:12px; }}"
                "QCheckBox::indicator { width:14px; height:14px; }"
                "QCheckBox::indicator:unchecked { background:#2a2a2a; border:1px solid #444; border-radius:3px; }"
                "QCheckBox::indicator:checked   { background:#4a9eff; border:1px solid #4a9eff; border-radius:3px; }"
                "QCheckBox::indicator:disabled  { background:#1a1a1a; border:1px solid #333; border-radius:3px; }"
            )
            self._checkboxes[code] = cb

            status = QLabel("✅" if installed else "")
            status.setStyleSheet("color:#4caf50; font-size:11px; min-width:80px;")
            self._status_labels[code] = status

            row = idx // COLS
            col_cb = (idx % COLS) * 2
            grid.addWidget(cb, row, col_cb)
            grid.addWidget(status, row, col_cb + 1)

        scroll.setWidget(grid_w)
        layout.addWidget(scroll)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border:none; background:#2a2a2a; border-radius:3px; }
            QProgressBar::chunk { background:#4a9eff; border-radius:3px; }
        """)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#888; font-size:12px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#2a2a2a;")
        layout.addWidget(sep)

        btn_row = QHBoxLayout()

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.setStyleSheet(
            "QPushButton { background:#2a2a2a; color:#888; border:1px solid #3a3a3a;"
            " border-radius:8px; padding:8px 24px; }"
            "QPushButton:hover { background:#333; color:#ccc; }"
        )
        self.close_btn.clicked.connect(self.accept)

        self.install_btn = QPushButton("⬇  Установить выбранные")
        self.install_btn.setStyleSheet(
            "QPushButton { background:#27ae60; color:white; border:none;"
            " border-radius:8px; padding:8px 28px; font-weight:bold; }"
            "QPushButton:hover { background:#2ecc71; }"
            "QPushButton:disabled { background:#1a3a2a; color:#555; }"
        )
        self.install_btn.clicked.connect(self._start_download)

        btn_row.addWidget(self.close_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.install_btn)
        layout.addLayout(btn_row)

    def _quick_select(self, codes: list[str]):
        for code, cb in self._checkboxes.items():
            if cb.isEnabled():
                cb.setChecked(code in codes)

    def _start_download(self):
        to_install = [
            code for code, cb in self._checkboxes.items()
            if cb.isChecked() and cb.isEnabled()
        ]
        if not to_install:
            self.status_label.setText("Ничего не выбрано.")
            return

        self.install_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Скачиваю {len(to_install)} языков…")

        self._download_thread = LangDownloadThread(to_install)
        self._download_thread.lang_started.connect(self._on_lang_started)
        self._download_thread.lang_progress.connect(self._on_lang_progress)
        self._download_thread.lang_done.connect(self._on_lang_done)
        self._download_thread.lang_error.connect(self._on_lang_error)
        self._download_thread.all_done.connect(self._on_all_done)
        self._download_thread.start()

    def _on_lang_started(self, code: str):
        name = LANG_NAMES.get(code, code)
        self.status_label.setText(f"⬇ {name} [{code}]…")
        self._status_labels[code].setText("⬇…")
        self._status_labels[code].setStyleSheet("color:#4a9eff; font-size:11px;")
        self.progress_bar.setValue(0)

    def _on_lang_progress(self, code: str, pct: int):
        self.progress_bar.setValue(pct)
        self._status_labels[code].setText(f"{pct}%")

    def _on_lang_done(self, code: str):
        self._status_labels[code].setText("✅")
        self._status_labels[code].setStyleSheet("color:#4caf50; font-size:11px;")
        cb = self._checkboxes[code]
        cb.setChecked(False)
        cb.setEnabled(False)
        self.langs_changed.emit()

    def _on_lang_error(self, code: str, msg: str):
        self._status_labels[code].setText("❌")
        self._status_labels[code].setStyleSheet("color:#f44336; font-size:11px;")
        self._status_labels[code].setToolTip(msg)

    def _on_all_done(self):
        self.install_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("✅ Готово!")
        self.langs_changed.emit()

    def closeEvent(self, event):
        if self._download_thread and self._download_thread.isRunning():
            self._download_thread.cancel()
            self._download_thread.wait(2000)
        super().closeEvent(event)
