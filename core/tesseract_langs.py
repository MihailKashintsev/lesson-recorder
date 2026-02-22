"""
Управление языковыми пакетами Tesseract OCR.

Языки ищутся в:
  1. Рядом с tesseract.exe (динамически)
  2. ~/.lesson_recorder/tessdata/
  3. Стандартные пути Windows
"""
import os
import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QScrollArea, QWidget, QGridLayout, QCheckBox, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

USER_TESSDATA     = Path.home() / ".lesson_recorder" / "tessdata"
TESSDATA_BASE_URL = "https://github.com/tesseract-ocr/tessdata/raw/main"
_SKIP_STEMS       = {"snum", "pdf", "configs", "tessconfigs", "osd", ""}

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


# ── Поиск Tesseract ───────────────────────────────────────────────────────────

def find_tesseract_cmd() -> str | None:
    """
    Ищет tesseract.exe: стандартные пути → PATH → реестр Windows
    → рядом с найденными tessdata → домашняя папка пользователя.
    """
    # 1. Стандартные пути
    for p in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Tesseract-OCR\tesseract.exe",
        r"C:\Tesseract\tesseract.exe",
        r"C:\tools\Tesseract-OCR\tesseract.exe",
        r"C:\Users\Public\Tesseract-OCR\tesseract.exe",
    ]:
        if Path(p).exists():
            return p

    # 2. PATH
    found = shutil.which("tesseract")
    if found:
        return found

    # 3. Реестр Windows (самый надёжный способ)
    try:
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for sub in [r"SOFTWARE\Tesseract-OCR", r"SOFTWARE\WOW6432Node\Tesseract-OCR"]:
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

    # 4. Рядом с tessdata папками (tessdata есть — exe на уровень выше)
    for tessdata_path in [
        r"C:\Program Files\Tesseract-OCR\tessdata",
        r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
        r"C:\Tesseract-OCR\tessdata",
    ]:
        td = Path(tessdata_path)
        if td.exists():
            exe = td.parent / "tesseract.exe"
            if exe.exists():
                return str(exe)

    # 5. Поиск в домашней папке пользователя (последний resort)
    try:
        for exe in Path.home().rglob("tesseract.exe"):
            return str(exe)
    except (PermissionError, OSError):
        pass

    return None


def get_all_tessdata_dirs() -> list[Path]:
    """
    Возвращает все tessdata папки: рядом с exe, пользовательская, стандартные.
    """
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
        # TESSDATA_PREFIX: USER_TESSDATA если там есть файлы, иначе рядом с exe
        if USER_TESSDATA.exists() and any(USER_TESSDATA.glob("*.traineddata")):
            os.environ["TESSDATA_PREFIX"] = str(USER_TESSDATA)
        else:
            exe_td = Path(cmd).parent / "tessdata"
            if exe_td.exists():
                os.environ["TESSDATA_PREFIX"] = str(exe_td)
        return True
    except ImportError:
        return False


# ── tessdata утилиты ──────────────────────────────────────────────────────────

def ensure_user_tessdata() -> Path:
    USER_TESSDATA.mkdir(parents=True, exist_ok=True)
    return USER_TESSDATA


def get_lang_file(code: str, tessdata_dir: Path) -> Path:
    return tessdata_dir / f"{code}.traineddata"


def is_lang_available(code: str) -> bool:
    return any(get_lang_file(code, d).exists() for d in get_all_tessdata_dirs())


def get_available_langs() -> list[str]:
    """Сканирует ВСЕ tessdata папки и возвращает отсортированный список языков."""
    langs: set[str] = set()
    for d in get_all_tessdata_dirs():
        for f in d.glob("*.traineddata"):
            if f.stem not in _SKIP_STEMS:
                langs.add(f.stem)
    return sorted(langs)


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

    # Ищем языки сначала в USER_TESSDATA (там уже всё скопировано)
    available = [c for c in lang_codes if get_lang_file(c, USER_TESSDATA).exists()]

    if not available:
        # Ищем в других директориях
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


# ── Поток скачивания ──────────────────────────────────────────────────────────

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
            # Копируем из системной если есть
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
                # Скачиваем с GitHub
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
    langs_changed = pyqtSignal()

    def __init__(self, preselect: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Установка языков OCR")
        self.setMinimumSize(560, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog { background:#1a1a1a; color:#e0e0e0; } QLabel { color:#e0e0e0; }")
        self._preselect  = set(preselect or [])
        self._checkboxes: dict[str, QCheckBox] = {}
        self._status_lbl: dict[str, QLabel]    = {}
        self._thread: LangDownloadThread | None = None
        self._available  = set(get_available_langs())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        layout.addWidget(QLabel("🌍  Языковые пакеты Tesseract OCR",
            styleSheet="font-size:15px; font-weight:bold;"))

        dirs = get_all_tessdata_dirs()
        info_text = ("Найдены tessdata: " + ", ".join(str(d) for d in dirs)
                     if dirs else "⚠️ tessdata не найдена — установи Tesseract")
        info = QLabel(info_text)
        info.setStyleSheet("color:#4a9eff; font-size:11px; background:#1a2a3a; border-radius:4px; padding:5px 8px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        quick = QHBoxLayout()
        for cap, codes in [("🇷🇺 Рус+Eng", ["rus","eng"]),
                            ("🇪🇺 Европа",  ["rus","eng","deu","fra","spa","ita","por","pol","ukr"]),
                            ("Все",         DOWNLOADABLE_LANGS), ("Снять", [])]:
            b = QPushButton(cap)
            b.setFixedHeight(26)
            b.setStyleSheet("QPushButton{background:#2a2a2a;color:#aaa;border:1px solid #3a3a3a;border-radius:5px;padding:0 10px;font-size:11px;}QPushButton:hover{background:#333;color:#fff;}")
            _c = list(codes)
            b.clicked.connect(lambda _, c=_c: self._quick(c))
            quick.addWidget(b)
        quick.addStretch()
        layout.addLayout(quick)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:1px solid #2a2a2a;border-radius:8px;background:#111;}")
        gw = QWidget(); gw.setStyleSheet("background:transparent;")
        grid = QGridLayout(gw)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(20); grid.setVerticalSpacing(6)
        COLS = 2
        for idx, code in enumerate(DOWNLOADABLE_LANGS):
            ok = code in self._available
            cb = QCheckBox(f"{LANG_NAMES.get(code, code)}  [{code}]")
            cb.setChecked(code in self._preselect and not ok)
            cb.setEnabled(not ok)
            cb.setStyleSheet(
                f"QCheckBox{{color:{'#555' if ok else '#d0d0d0'};font-size:12px;}}"
                "QCheckBox::indicator{width:14px;height:14px;}"
                "QCheckBox::indicator:unchecked{background:#2a2a2a;border:1px solid #444;border-radius:3px;}"
                "QCheckBox::indicator:checked{background:#4a9eff;border:1px solid #4a9eff;border-radius:3px;}"
                "QCheckBox::indicator:disabled{background:#1a1a1a;border:1px solid #333;border-radius:3px;}"
            )
            self._checkboxes[code] = cb
            sl = QLabel("✅" if ok else "")
            sl.setStyleSheet("color:#4caf50;font-size:11px;min-width:60px;")
            self._status_lbl[code] = sl
            r = idx // COLS; c = (idx % COLS) * 2
            grid.addWidget(cb, r, c)
            grid.addWidget(sl, r, c + 1)
        scroll.setWidget(gw)
        layout.addWidget(scroll)

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100); self.pbar.setFixedHeight(6); self.pbar.setVisible(False)
        self.pbar.setStyleSheet("QProgressBar{border:none;background:#2a2a2a;border-radius:3px;}QProgressBar::chunk{background:#4a9eff;border-radius:3px;}")
        layout.addWidget(self.pbar)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#888;font-size:12px;"); self.status.setWordWrap(True)
        layout.addWidget(self.status)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setStyleSheet("color:#2a2a2a;")
        layout.addWidget(sep)

        row = QHBoxLayout()
        close = QPushButton("Закрыть")
        close.setStyleSheet("QPushButton{background:#2a2a2a;color:#888;border:1px solid #3a3a3a;border-radius:8px;padding:8px 24px;}QPushButton:hover{background:#333;color:#ccc;}")
        close.clicked.connect(self.accept)
        self.install_btn = QPushButton("⬇  Установить выбранные")
        self.install_btn.setStyleSheet("QPushButton{background:#27ae60;color:white;border:none;border-radius:8px;padding:8px 28px;font-weight:bold;}QPushButton:hover{background:#2ecc71;}QPushButton:disabled{background:#1a3a2a;color:#555;}")
        self.install_btn.clicked.connect(self._start)
        row.addWidget(close); row.addStretch(); row.addWidget(self.install_btn)
        layout.addLayout(row)

    def _quick(self, codes):
        for code, cb in self._checkboxes.items():
            if cb.isEnabled():
                cb.setChecked(code in codes)

    def _start(self):
        to_do = [c for c, cb in self._checkboxes.items() if cb.isChecked() and cb.isEnabled()]
        if not to_do:
            self.status.setText("Ничего не выбрано.")
            return
        self.install_btn.setEnabled(False)
        self.pbar.setVisible(True)
        self.status.setText(f"Скачиваю {len(to_do)} языков…")
        self._thread = LangDownloadThread(to_do)
        self._thread.lang_started.connect(lambda c: (
            self.status.setText(f"⬇ {LANG_NAMES.get(c,c)} [{c}]…"),
            self._status_lbl[c].setText("⬇…"),
            self._status_lbl[c].setStyleSheet("color:#4a9eff;font-size:11px;"),
            self.pbar.setValue(0)
        ))
        self._thread.lang_progress.connect(lambda c, p: (
            self.pbar.setValue(p), self._status_lbl[c].setText(f"{p}%")
        ))
        self._thread.lang_done.connect(self._done_one)
        self._thread.lang_error.connect(lambda c, e: (
            self._status_lbl[c].setText("❌"),
            self._status_lbl[c].setStyleSheet("color:#f44336;font-size:11px;"),
            self._status_lbl[c].setToolTip(e)
        ))
        self._thread.all_done.connect(self._all_done)
        self._thread.start()

    def _done_one(self, code):
        self._status_lbl[code].setText("✅")
        self._status_lbl[code].setStyleSheet("color:#4caf50;font-size:11px;")
        self._checkboxes[code].setChecked(False)
        self._checkboxes[code].setEnabled(False)
        self.langs_changed.emit()

    def _all_done(self):
        self.install_btn.setEnabled(True)
        self.pbar.setVisible(False)
        self.status.setText("✅ Готово!")
        self.langs_changed.emit()

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._thread.cancel(); self._thread.wait(2000)
        super().closeEvent(event)
