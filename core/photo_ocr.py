"""
Модуль для добавления фотографий и распознавания текста (OCR).

Поддерживает:
  - Выбор файла с диска (JPG, PNG, BMP, TIFF, WebP)
  - Съёмку с веб-камеры (если доступна)
  - OCR через pytesseract с поддержкой любого количества языков одновременно
  - Автоопределение установленных языковых пакетов Tesseract

Установка Tesseract (Windows):
  https://github.com/UB-Mannheim/tesseract/wiki
  При установке выбрать нужные языковые пакеты.
"""
import os
import tempfile

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QScrollArea, QWidget, QMessageBox,
    QCheckBox, QFrame, QGridLayout,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

# Стандартный путь установки Tesseract на Windows
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Человекочитаемые имена языков (код Tesseract → название)
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
    "srp": "Српски",
    "ces": "Čeština",
    "slk": "Slovenčina",
    "hun": "Magyar",
    "ron": "Română",
    "hrv": "Hrvatski",
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
    "msa": "Bahasa Melayu",
    "kat": "ქართული",
    "ell": "Ελληνικά",
    "lav": "Latviešu",
    "lit": "Lietuvių",
    "est": "Eesti",
    "equ": "Формулы/Math",
    "osd": "OSD (авто)",
}

# Языки по умолчанию (если установлены)
DEFAULT_LANGS = ["rus", "eng"]


def _setup_tesseract():
    """Настраивает путь к tesseract.exe."""
    try:
        import pytesseract
        if os.path.exists(TESSERACT_CMD):
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    except ImportError:
        pass


def _tesseract_available() -> bool:
    try:
        import pytesseract
        _setup_tesseract()
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _get_installed_langs() -> list[str]:
    """Возвращает список установленных языков Tesseract."""
    try:
        import pytesseract
        _setup_tesseract()
        langs = pytesseract.get_languages(config="")
        skip = {"snum"}   # служебные пакеты без языка
        return [ln for ln in langs if ln not in skip]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────

class OcrThread(QThread):
    """Фоновый поток распознавания текста на нескольких фото."""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, image_paths: list[str], lang_string: str):
        super().__init__()
        self.image_paths = image_paths
        self.lang_string = lang_string or "eng"

    def run(self):
        try:
            import pytesseract
            from PIL import Image
            _setup_tesseract()

            parts = []
            for i, path in enumerate(self.image_paths, 1):
                self.progress.emit(
                    i, len(self.image_paths),
                    f"Фото {i}/{len(self.image_paths)}  [{self.lang_string}]…"
                )
                img = Image.open(path)
                try:
                    text = pytesseract.image_to_string(img, lang=self.lang_string).strip()
                except Exception:
                    # fallback: пробуем eng
                    try:
                        text = pytesseract.image_to_string(img, lang="eng").strip()
                    except Exception:
                        text = pytesseract.image_to_string(img).strip()

                if text:
                    parts.append(f"[Фото {i}]\n{text}")

            self.finished.emit("\n\n".join(parts) if parts else "")

        except ImportError:
            self.error.emit(
                "Не установлен pytesseract или Pillow.\n"
                "Выполни: pip install pytesseract Pillow"
            )
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────

class CameraDialog(QDialog):
    """Диалог съёмки с веб-камеры."""
    photo_taken = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Камера")
        self.setFixedSize(700, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog { background: #1a1a1a; } QLabel { color: #e0e0e0; }")

        self._cap       = None
        self._timer_id  = None
        self._last_frame = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self.view_label = QLabel("Инициализация камеры…")
        self.view_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view_label.setFixedSize(660, 460)
        self.view_label.setStyleSheet("background: #0d0d0d; border-radius: 8px;")
        layout.addWidget(self.view_label)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet(
            "QPushButton { background:#2a2a2a; color:#aaa; border:1px solid #3a3a3a;"
            " border-radius:8px; padding:8px 24px; }"
            "QPushButton:hover { background:#333; color:#fff; }"
        )
        cancel_btn.clicked.connect(self.reject)

        self.snap_btn = QPushButton("📷  Сфотографировать")
        self.snap_btn.setEnabled(False)
        self.snap_btn.setStyleSheet(
            "QPushButton { background:#27ae60; color:white; border:none;"
            " border-radius:8px; padding:8px 24px; font-weight:bold; }"
            "QPushButton:hover { background:#2ecc71; }"
            "QPushButton:disabled { background:#1a3a2a; color:#555; }"
        )
        self.snap_btn.clicked.connect(self._take_photo)

        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.snap_btn)
        layout.addLayout(btn_row)

        self._start_camera()

    def _start_camera(self):
        try:
            import cv2
            self._cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                self.view_label.setText("❌ Камера не найдена")
                return
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.snap_btn.setEnabled(True)
            self._timer_id = self.startTimer(33)
        except ImportError:
            self.view_label.setText(
                "opencv-python не установлен.\n"
                "Выполни: pip install opencv-python"
            )

    def timerEvent(self, event):
        if self._cap is None:
            return
        import cv2
        ret, frame = self._cap.read()
        if not ret:
            return
        self._last_frame = frame
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self.view_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.view_label.setPixmap(pix)

    def _take_photo(self):
        if self._last_frame is None:
            return
        import cv2
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False,
                                          dir=tempfile.gettempdir())
        tmp.close()
        cv2.imwrite(tmp.name, self._last_frame)
        self._cleanup()
        self.photo_taken.emit(tmp.name)
        self.accept()

    def _cleanup(self):
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def reject(self):
        self._cleanup()
        super().reject()

    def closeEvent(self, event):
        self._cleanup()
        super().closeEvent(event)


# ─────────────────────────────────────────────────────────────────────────────

class LangSelectorWidget(QWidget):
    """
    Виджет выбора языков OCR.
    Динамически отображает только реально установленные языки.
    """
    selection_changed = pyqtSignal()

    def __init__(self, installed_langs: list[str], parent=None):
        super().__init__(parent)
        self._checkboxes: dict[str, QCheckBox] = {}
        self._build(installed_langs)

    def _build(self, installed_langs: list[str]):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        if not installed_langs:
            lbl = QLabel("Языковые пакеты не найдены.\nУстанови Tesseract с нужными языками.")
            lbl.setStyleSheet("color: #888; font-size: 12px;")
            outer.addWidget(lbl)
            # Пустая строка итога
            self._summary_lbl = QLabel("")
            return

        # ── Заголовок + быстрые кнопки ───────────────────────────────────
        header_row = QHBoxLayout()
        lbl = QLabel(f"Языки OCR  ({len(installed_langs)} установлено):")
        lbl.setStyleSheet("color: #ccc; font-size: 12px; font-weight: bold;")
        header_row.addWidget(lbl)
        header_row.addStretch()

        for caption, slot in [("Все", self._select_all), ("Снять всё", self._select_none)]:
            btn = QPushButton(caption)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                "QPushButton { background:#2a2a2a; color:#aaa; border:1px solid #3a3a3a;"
                " border-radius:4px; padding:0 8px; font-size:11px; }"
                "QPushButton:hover { background:#3a3a3a; color:#fff; }"
            )
            btn.clicked.connect(slot)
            header_row.addWidget(btn)

        outer.addLayout(header_row)

        # ── Прокручиваемая сетка чекбоксов ──────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(130)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: #111; border: 1px solid #2a2a2a; border-radius: 6px; }"
        )

        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(5)

        COLS = 3
        for idx, code in enumerate(installed_langs):
            name = LANG_NAMES.get(code, code.upper())
            cb = QCheckBox(f"{name}  [{code}]")
            cb.setStyleSheet(
                "QCheckBox { color: #d0d0d0; font-size: 12px; }"
                "QCheckBox::indicator { width: 14px; height: 14px; }"
                "QCheckBox::indicator:unchecked { background:#2a2a2a; border:1px solid #444;"
                "  border-radius:3px; }"
                "QCheckBox::indicator:checked  { background:#4a9eff; border:1px solid #4a9eff;"
                "  border-radius:3px; }"
            )
            cb.setChecked(code in DEFAULT_LANGS)
            cb.stateChanged.connect(self._on_change)
            self._checkboxes[code] = cb
            grid.addWidget(cb, idx // COLS, idx % COLS)

        scroll.setWidget(grid_w)
        outer.addWidget(scroll)

        # ── Строка итоговой строки языков ────────────────────────────────
        self._summary_lbl = QLabel()
        self._summary_lbl.setStyleSheet("color: #4a9eff; font-size: 11px;")
        outer.addWidget(self._summary_lbl)
        self._update_summary()

    def _on_change(self):
        self._update_summary()
        self.selection_changed.emit()

    def _update_summary(self):
        langs = self.get_selected_langs()
        if langs:
            names = [LANG_NAMES.get(c, c) for c in langs]
            self._summary_lbl.setText(
                f"Выбрано: {', '.join(names)}  →  строка: {'+'.join(langs)}"
            )
        else:
            self._summary_lbl.setText("⚠️ Выбери хотя бы один язык")

    def _select_all(self):
        for cb in self._checkboxes.values():
            cb.setChecked(True)

    def _select_none(self):
        for cb in self._checkboxes.values():
            cb.setChecked(False)

    def get_selected_langs(self) -> list[str]:
        return [code for code, cb in self._checkboxes.items() if cb.isChecked()]

    def get_lang_string(self) -> str:
        langs = self.get_selected_langs()
        return "+".join(langs) if langs else "eng"


# ─────────────────────────────────────────────────────────────────────────────

class PhotoThumbnail(QWidget):
    """Миниатюра фото с кнопкой удаления."""
    removed = pyqtSignal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.setFixedSize(110, 130)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        img_label = QLabel()
        img_label.setFixedSize(100, 100)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setStyleSheet("background:#0d0d0d; border-radius:6px;")
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        img_label.setPixmap(pix)
        layout.addWidget(img_label)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedHeight(22)
        remove_btn.setStyleSheet(
            "QPushButton { background:#3a1a1a; color:#f44336; border:none;"
            " border-radius:4px; font-size:11px; }"
            "QPushButton:hover { background:#5a2a2a; }"
        )
        remove_btn.clicked.connect(lambda: self.removed.emit(self.path))
        layout.addWidget(remove_btn)


# ─────────────────────────────────────────────────────────────────────────────

class PhotoOcrDialog(QDialog):
    """
    Главный диалог:
    1. Пользователь добавляет фото (с диска или камеры)
    2. Выбирает языки OCR из автоматически найденных установленных пакетов
    3. Нажимает «Распознать» — OCR в фоне
    4. Результат: .get_ocr_text()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Фото → Текст")
        self.setMinimumSize(660, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("""
            QDialog  { background: #1a1a1a; color: #e0e0e0; }
            QLabel   { color: #e0e0e0; }
            QScrollArea { background: transparent; border: none; }
        """)

        self._photos: list[str] = []
        self._ocr_text: str = ""
        self._ocr_thread: OcrThread | None = None

        # Загружаем установленные языки синхронно (очень быстро)
        self._installed_langs: list[str] = (
            _get_installed_langs() if _tesseract_available() else []
        )

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        # ── Заголовок ────────────────────────────────────────────────────
        hdr = QLabel("📷  Добавьте фотографии досок, слайдов или заметок")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(hdr)

        hint = QLabel("Текст с фото будет распознан и добавлен к конспекту.")
        hint.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(hint)

        # ── Кнопки добавления ────────────────────────────────────────────
        add_row = QHBoxLayout()
        self.add_file_btn = QPushButton("🖼  Выбрать файл")
        self.add_file_btn.setStyleSheet(self._btn_style("#2a5298"))
        self.add_file_btn.clicked.connect(self._pick_files)

        self.add_camera_btn = QPushButton("📷  Сфотографировать")
        self.add_camera_btn.setStyleSheet(self._btn_style("#27ae60"))
        self.add_camera_btn.clicked.connect(self._open_camera)

        add_row.addWidget(self.add_file_btn)
        add_row.addWidget(self.add_camera_btn)
        add_row.addStretch()
        layout.addLayout(add_row)

        # ── Лента миниатюр ───────────────────────────────────────────────
        photo_scroll = QScrollArea()
        photo_scroll.setFixedHeight(150)
        photo_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        photo_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        photo_scroll.setWidgetResizable(True)
        photo_scroll.setStyleSheet(
            "background: #111; border: 1px solid #2a2a2a; border-radius: 8px;"
        )

        self._thumb_container = QWidget()
        self._thumb_layout = QHBoxLayout(self._thumb_container)
        self._thumb_layout.setContentsMargins(8, 8, 8, 8)
        self._thumb_layout.setSpacing(8)
        self._thumb_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._empty_label = QLabel("Нет добавленных фото")
        self._empty_label.setStyleSheet("color: #444; font-size: 13px;")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_layout.addWidget(self._empty_label)

        photo_scroll.setWidget(self._thumb_container)
        layout.addWidget(photo_scroll)

        self._count_label = QLabel("0 фото добавлено")
        self._count_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._count_label)

        # ── Разделитель ──────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2a2a;")
        layout.addWidget(sep)

        # ── Выбор языков ─────────────────────────────────────────────────
        self._lang_selector = LangSelectorWidget(self._installed_langs, self)
        self._lang_selector.selection_changed.connect(self._update_recognize_btn)
        layout.addWidget(self._lang_selector)

        # Предупреждение если Tesseract не найден
        if not self._installed_langs:
            warn = QLabel(
                "⚠️ Tesseract не найден или языковые пакеты не установлены.\n"
                "Скачай: https://github.com/UB-Mannheim/tesseract/wiki  "
                "(при установке выбери нужные языки)"
            )
            warn.setStyleSheet(
                "color: #ffb300; font-size: 11px;"
                " background: #2a1f00; border-radius: 6px; padding: 6px 10px;"
            )
            warn.setWordWrap(True)
            layout.addWidget(warn)

        # ── Статус OCR ───────────────────────────────────────────────────
        self.ocr_status = QLabel("")
        self.ocr_status.setStyleSheet("color: #4caf50; font-size: 12px;")
        self.ocr_status.setWordWrap(True)
        layout.addWidget(self.ocr_status)

        # ── Кнопки действий ─────────────────────────────────────────────
        layout.addStretch()
        btn_row = QHBoxLayout()

        skip_btn = QPushButton("Пропустить")
        skip_btn.setStyleSheet(
            "QPushButton { background:#2a2a2a; color:#888; border:1px solid #3a3a3a;"
            " border-radius:8px; padding:8px 24px; }"
            "QPushButton:hover { background:#333; color:#ccc; }"
        )
        skip_btn.clicked.connect(self.reject)

        self.recognize_btn = QPushButton("🔍  Распознать текст")
        self.recognize_btn.setEnabled(False)
        self.recognize_btn.setStyleSheet(
            "QPushButton { background:#4a9eff; color:white; border:none;"
            " border-radius:8px; padding:8px 28px; font-weight:bold; }"
            "QPushButton:hover { background:#5aadff; }"
            "QPushButton:disabled { background:#1a3a5a; color:#555; }"
        )
        self.recognize_btn.clicked.connect(self._start_ocr)

        btn_row.addWidget(skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.recognize_btn)
        layout.addLayout(btn_row)

    # ── Добавление фото ───────────────────────────────────────────────────

    def _pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Выбери фотографии", "",
            "Изображения (*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp)"
        )
        for p in paths:
            self._add_photo(p)

    def _open_camera(self):
        try:
            import cv2  # noqa
        except ImportError:
            QMessageBox.information(
                self, "Камера недоступна",
                "Для работы камеры установи opencv-python:\n\npip install opencv-python"
            )
            return
        dlg = CameraDialog(self)
        dlg.photo_taken.connect(self._add_photo)
        dlg.exec()

    def _add_photo(self, path: str):
        if path in self._photos:
            return
        self._photos.append(path)
        if len(self._photos) == 1:
            self._empty_label.setVisible(False)
        thumb = PhotoThumbnail(path, self._thumb_container)
        thumb.removed.connect(self._remove_photo)
        self._thumb_layout.addWidget(thumb)
        self._update_count()

    def _remove_photo(self, path: str):
        if path not in self._photos:
            return
        self._photos.remove(path)
        for i in range(self._thumb_layout.count()):
            w = self._thumb_layout.itemAt(i).widget()
            if isinstance(w, PhotoThumbnail) and w.path == path:
                w.setParent(None)
                break
        if not self._photos:
            self._empty_label.setVisible(True)
        self._update_count()

    def _update_count(self):
        n = len(self._photos)
        self._count_label.setText(f"{n} фото добавлено" if n else "0 фото добавлено")
        self._update_recognize_btn()

    def _update_recognize_btn(self):
        has_photos   = len(self._photos) > 0
        has_langs    = bool(self._lang_selector.get_selected_langs())
        has_tesseract = bool(self._installed_langs)
        self.recognize_btn.setEnabled(has_photos and has_langs and has_tesseract)

    # ── OCR ───────────────────────────────────────────────────────────────

    def _start_ocr(self):
        lang_string = self._lang_selector.get_lang_string()
        if not lang_string:
            QMessageBox.warning(self, "Нет языков", "Выбери хотя бы один язык OCR.")
            return

        self.recognize_btn.setEnabled(False)
        self.add_file_btn.setEnabled(False)
        self.add_camera_btn.setEnabled(False)
        self.ocr_status.setText(f"⏳ Распознаю [{lang_string}]…")

        self._ocr_thread = OcrThread(list(self._photos), lang_string)
        self._ocr_thread.progress.connect(self._on_ocr_progress)
        self._ocr_thread.finished.connect(self._on_ocr_done)
        self._ocr_thread.error.connect(self._on_ocr_error)
        self._ocr_thread.start()

    def _on_ocr_progress(self, current: int, total: int, msg: str):
        self.ocr_status.setText(f"⏳ {msg}")

    def _on_ocr_done(self, text: str):
        self._ocr_text = text
        langs = self._lang_selector.get_lang_string()
        if text:
            self.ocr_status.setText(
                f"✅ Готово · {len(self._photos)} фото · "
                f"{len(text)} симв. · языки: {langs}"
            )
        else:
            self.ocr_status.setText("⚠️ Текст не найден на фотографиях")
        self.accept()

    def _on_ocr_error(self, msg: str):
        self.ocr_status.setText(f"❌ {msg}")
        self.recognize_btn.setEnabled(True)
        self.add_file_btn.setEnabled(True)
        self.add_camera_btn.setEnabled(True)

    # ── Результат ─────────────────────────────────────────────────────────

    def get_ocr_text(self) -> str:
        return self._ocr_text

    @staticmethod
    def _btn_style(color: str) -> str:
        return (
            f"QPushButton {{ background:{color}; color:white; border:none;"
            f" border-radius:8px; padding:8px 20px; }}"
            f"QPushButton:hover {{ background:{color}cc; }}"
        )