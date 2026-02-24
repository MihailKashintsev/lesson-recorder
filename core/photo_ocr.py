"""
Модуль фото + OCR. Импорты photo_ocr НЕ ломают запись —
tesseract_langs грузится лениво внутри методов.
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

DEFAULT_LANGS = ["rus", "eng"]


# ── Helpers — всё через lazy import чтобы не падал recording_widget ──────────

def _get_tl():
    """Lazy import tesseract_langs."""
    from core import tesseract_langs as tl
    return tl


def _tesseract_available() -> bool:
    try:
        tl = _get_tl()
        cmd = tl.find_tesseract_cmd()
        if not cmd:
            return False
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = cmd
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _get_installed_langs() -> list[str]:
    try:
        return _get_tl().get_available_langs()
    except Exception:
        return []


# ── Init Thread — поиск Tesseract в фоне, чтобы UI не зависал ────────────────

class TesseractInitThread(QThread):
    ready = pyqtSignal(bool, list)   # (tess_ok, installed_langs)

    def run(self):
        installed = []
        tess_ok   = False
        try:
            installed = _get_installed_langs()
            tess_ok   = _tesseract_available() or bool(installed)
        except Exception:
            pass
        self.ready.emit(tess_ok, installed)


# ── OCR Thread ────────────────────────────────────────────────────────────────

class OcrThread(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, image_paths: list[str], lang_codes: list[str]):
        super().__init__()
        self.image_paths = image_paths
        self.lang_codes  = lang_codes

    def run(self):
        try:
            import pytesseract
            from PIL import Image
            tl = _get_tl()
            tl.setup_tesseract()
            lang_string, tessdata_dir = tl.prepare_tessdata_for_ocr(self.lang_codes)
            if not lang_string:
                lang_string = "eng"

            parts = []
            for i, path in enumerate(self.image_paths, 1):
                self.progress.emit(i, len(self.image_paths),
                    f"Фото {i}/{len(self.image_paths)}  [{lang_string}]…")
                img = Image.open(path)
                try:
                    text = pytesseract.image_to_string(img, lang=lang_string).strip()
                except Exception:
                    try:
                        text = pytesseract.image_to_string(img, lang="eng").strip()
                    except Exception:
                        text = ""
                if text:
                    parts.append(f"[Фото {i}]\n{text}")

            self.finished.emit("\n\n".join(parts) if parts else "")
        except ImportError:
            self.error.emit("Не установлен pytesseract или Pillow.\n"
                            "Выполни: pip install pytesseract Pillow")
        except Exception as e:
            self.error.emit(str(e))


# ── Camera Dialog ─────────────────────────────────────────────────────────────

class CameraDialog(QDialog):
    photo_taken = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Камера")
        self.setFixedSize(700, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog{background:#1a1a1a;} QLabel{color:#e0e0e0;}")
        self._cap = self._timer_id = self._last_frame = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12); layout.setContentsMargins(20,20,20,20)

        self.view = QLabel("Инициализация камеры…")
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.setFixedSize(660, 460)
        self.view.setStyleSheet("background:#0d0d0d; border-radius:8px;")
        layout.addWidget(self.view)

        row = QHBoxLayout()
        cancel = QPushButton("Отмена")
        cancel.setStyleSheet("QPushButton{background:#2a2a2a;color:#aaa;border:1px solid #3a3a3a;border-radius:8px;padding:8px 24px;}QPushButton:hover{background:#333;color:#fff;}")
        cancel.clicked.connect(self.reject)
        self.snap = QPushButton("📷  Сфотографировать")
        self.snap.setEnabled(False)
        self.snap.setStyleSheet("QPushButton{background:#27ae60;color:white;border:none;border-radius:8px;padding:8px 24px;font-weight:bold;}QPushButton:hover{background:#2ecc71;}QPushButton:disabled{background:#1a3a2a;color:#555;}")
        self.snap.clicked.connect(self._take)
        row.addWidget(cancel); row.addStretch(); row.addWidget(self.snap)
        layout.addLayout(row)
        self._start_camera()

    def _start_camera(self):
        try:
            import cv2
            self._cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                self.view.setText("❌ Камера не найдена")
                return
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.snap.setEnabled(True)
            self._timer_id = self.startTimer(33)
        except ImportError:
            self.view.setText("opencv-python не установлен.\npip install opencv-python")

    def timerEvent(self, event):
        if not self._cap: return
        import cv2
        ret, frame = self._cap.read()
        if not ret: return
        self._last_frame = frame
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        pix = QPixmap.fromImage(QImage(rgb.data, w, h, ch*w, QImage.Format.Format_RGB888))
        self.view.setPixmap(pix.scaled(self.view.size(),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _take(self):
        if self._last_frame is None: return
        import cv2
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, dir=tempfile.gettempdir())
        tmp.close(); cv2.imwrite(tmp.name, self._last_frame)
        self._cleanup(); self.photo_taken.emit(tmp.name); self.accept()

    def _cleanup(self):
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
        if self._cap:
            self._cap.release(); self._cap = None

    def reject(self): self._cleanup(); super().reject()
    def closeEvent(self, e): self._cleanup(); super().closeEvent(e)


# ── Lang Selector ─────────────────────────────────────────────────────────────

class LangSelectorWidget(QWidget):
    selection_changed = pyqtSignal()
    install_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, installed_langs: list[str], parent=None):
        super().__init__(parent)
        self._checkboxes:  dict[str, QCheckBox] = {}
        self._summary_lbl  = QLabel()
        self._install_btn  = None   # ссылка для блокировки
        self._refresh_btn  = None
        self._checking     = False
        QVBoxLayout(self)
        self._build(installed_langs)

    def set_checking(self, checking: bool):
        """Блокирует кнопки пока идёт фоновая проверка Tesseract."""
        self._checking = checking
        if self._install_btn:
            self._install_btn.setEnabled(not checking)
            self._install_btn.setText(
                "🔍 Проверяю…" if checking else "🌍 Установить языки…"
            )
        if self._refresh_btn:
            self._refresh_btn.setEnabled(not checking)

    def _build(self, installed_langs: list[str]):
        layout = self.layout()
        # Чистим
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checkboxes.clear()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        try:
            from core.tesseract_langs import LANG_NAMES
        except Exception:
            LANG_NAMES = {}

        # ── Заголовок ────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        lbl = QLabel(f"Языки OCR  ({len(installed_langs)} установлено):"
                     if installed_langs else "Языки OCR  (не найдены):")
        lbl.setStyleSheet("color:#ccc; font-size:12px; font-weight:bold;")
        hdr.addWidget(lbl)
        hdr.addStretch()

        # Кнопка Обновить — всегда видна, перечитывает tessdata
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.setFixedHeight(22)
        refresh_btn.setStyleSheet(
            "QPushButton{background:#2a3a2a;color:#4caf50;border:1px solid #3a5a3a;"
            "border-radius:4px;padding:0 8px;font-size:11px;}"
            "QPushButton:hover{background:#3a5a3a;color:#6adf6a;}"
            "QPushButton:disabled{background:#1a1a1a;color:#555;border-color:#333;}")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        self._refresh_btn = refresh_btn
        hdr.addWidget(refresh_btn)

        if installed_langs:
            for cap, fn in [("Все", self._all), ("Снять", self._none)]:
                b = QPushButton(cap)
                b.setFixedHeight(22)
                b.setStyleSheet("QPushButton{background:#2a2a2a;color:#aaa;border:1px solid #3a3a3a;border-radius:4px;padding:0 8px;font-size:11px;}QPushButton:hover{background:#3a3a3a;color:#fff;}")
                b.clicked.connect(fn)
                hdr.addWidget(b)

        install_btn = QPushButton("🔍 Проверяю…" if self._checking else "🌍 Установить языки…")
        install_btn.setFixedHeight(22)
        install_btn.setEnabled(not self._checking)
        install_btn.setStyleSheet(
            "QPushButton{background:#27ae60;color:white;border:none;border-radius:4px;padding:0 10px;font-size:11px;}"
            "QPushButton:hover{background:#2ecc71;}"
            "QPushButton:disabled{background:#1a3a2a;color:#555;}")
        install_btn.clicked.connect(self.install_requested.emit)
        self._install_btn = install_btn
        hdr.addWidget(install_btn)
        layout.addLayout(hdr)

        if not installed_langs:
            hint = QLabel("Нажми «Обновить» или «Установить языки».")
            hint.setStyleSheet("color:#555; font-size:11px;")
            layout.addWidget(hint)
            self._summary_lbl = QLabel("")
            layout.addWidget(self._summary_lbl)
            return

        # ── Сетка чекбоксов ──────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(120)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:#111;border:1px solid #2a2a2a;border-radius:6px;}")
        gw = QWidget(); gw.setStyleSheet("background:transparent;")
        grid = QGridLayout(gw)
        grid.setContentsMargins(8,8,8,8); grid.setHorizontalSpacing(16); grid.setVerticalSpacing(5)
        COLS = 3
        for idx, code in enumerate(installed_langs):
            name = LANG_NAMES.get(code, code.upper())
            cb = QCheckBox(f"{name}  [{code}]")
            cb.setStyleSheet(
                "QCheckBox{color:#d0d0d0;font-size:12px;}"
                "QCheckBox::indicator{width:14px;height:14px;}"
                "QCheckBox::indicator:unchecked{background:#2a2a2a;border:1px solid #444;border-radius:3px;}"
                "QCheckBox::indicator:checked{background:#4a9eff;border:1px solid #4a9eff;border-radius:3px;}"
            )
            cb.setChecked(code in DEFAULT_LANGS)
            cb.stateChanged.connect(self._changed)
            self._checkboxes[code] = cb
            grid.addWidget(cb, idx // COLS, idx % COLS)
        scroll.setWidget(gw)
        layout.addWidget(scroll)

        self._summary_lbl = QLabel()
        self._summary_lbl.setStyleSheet("color:#4a9eff; font-size:11px;")
        layout.addWidget(self._summary_lbl)
        self._update_summary()

    def _changed(self): self._update_summary(); self.selection_changed.emit()

    def _update_summary(self):
        langs = self.get_selected_langs()
        try:
            from core.tesseract_langs import LANG_NAMES
        except Exception:
            LANG_NAMES = {}
        if langs:
            names = [LANG_NAMES.get(c, c) for c in langs]
            self._summary_lbl.setText(f"Выбрано: {', '.join(names)}  →  {'+'.join(langs)}")
        else:
            self._summary_lbl.setText("⚠️ Выбери хотя бы один язык")

    def _all(self):
        for cb in self._checkboxes.values(): cb.setChecked(True)
    def _none(self):
        for cb in self._checkboxes.values(): cb.setChecked(False)

    def get_selected_langs(self) -> list[str]:
        return [c for c, cb in self._checkboxes.items() if cb.isChecked()]

    def reload(self, installed_langs: list[str]):
        prev = self.get_selected_langs()
        self._build(installed_langs)
        for code in prev:
            if code in self._checkboxes:
                self._checkboxes[code].setChecked(True)
        self.selection_changed.emit()


# ── Photo Thumbnail ───────────────────────────────────────────────────────────

class PhotoThumbnail(QWidget):
    removed = pyqtSignal(str)
    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path; self.setFixedSize(110, 130)
        layout = QVBoxLayout(self); layout.setContentsMargins(4,4,4,4); layout.setSpacing(4)
        img = QLabel(); img.setFixedSize(100, 100)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet("background:#0d0d0d; border-radius:6px;")
        # ✅ ИСПРАВЛЕНО: SmoothTransformation на больших фото (12МП+) тормозила UI.
        # Теперь: сначала быстрый FastTransformation до 300px, потом Smooth до 100px.
        # Итог: качество сохранено, скорость ~10x выше.
        pix = QPixmap(path)
        if not pix.isNull():
            if pix.width() > 300 or pix.height() > 300:
                pix = pix.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.FastTransformation)
            pix = pix.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        img.setPixmap(pix); layout.addWidget(img)
        rm = QPushButton("✕"); rm.setFixedHeight(22)
        rm.setStyleSheet("QPushButton{background:#3a1a1a;color:#f44336;border:none;border-radius:4px;font-size:11px;}QPushButton:hover{background:#5a2a2a;}")
        rm.clicked.connect(lambda: self.removed.emit(self.path))
        layout.addWidget(rm)


# ── Main Dialog ───────────────────────────────────────────────────────────────

class PhotoOcrDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Фото → Текст")
        self.setMinimumSize(660, 620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog{background:#1a1a1a;color:#e0e0e0;} QLabel{color:#e0e0e0;}")

        self._photos: list[str]            = []
        self._ocr_text: str                = ""
        self._ocr_thread: OcrThread | None = None
        self._installed: list[str]         = []
        self._tess_ok: bool                = False

        # ✅ ИСПРАВЛЕНО: UI строится сразу (диалог не висит),
        # поиск Tesseract идёт в фоновом потоке.
        self._build_ui()

        # Блокируем кнопки пока идёт проверка
        self._lang_sel.set_checking(True)

        self._init_thread = TesseractInitThread(self)
        self._init_thread.ready.connect(self._on_tess_ready)
        self._init_thread.start()

    def _on_tess_ready(self, tess_ok: bool, installed: list):
        """Вызывается из фонового потока когда Tesseract найден/не найден."""
        self._tess_ok   = tess_ok
        self._installed = installed
        self._lang_sel.set_checking(False)    # ← разблокируем кнопки
        self._lang_sel.reload(installed)
        self._upd_btn()

        if installed:
            self._ocr_status.setStyleSheet("color:#4caf50; font-size:12px;")
            self._ocr_status.setText(
                f"✅ Tesseract готов · {len(installed)} языков"
                + (f" ({', '.join(installed[:4])}{'…' if len(installed)>4 else ''})" if installed else "")
            )
        else:
            self._ocr_status.setStyleSheet("color:#ffb300; font-size:12px;")
            self._ocr_status.setText(
                "⚠️ Tesseract не найден. Нажми «Установить языки» → вкладка «Tesseract»"
            )

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14); layout.setContentsMargins(24,24,24,24)

        layout.addWidget(QLabel("📷  Добавьте фотографии досок, слайдов или заметок",
            styleSheet="font-size:15px;font-weight:bold;color:#e0e0e0;"))
        layout.addWidget(QLabel("Текст с фото будет распознан и добавлен к конспекту.",
            styleSheet="color:#888;font-size:12px;"))

        row = QHBoxLayout()
        self.file_btn = QPushButton("🖼  Выбрать файл")
        self.file_btn.setStyleSheet(self._btn("#2a5298"))
        self.file_btn.clicked.connect(self._pick)
        self.cam_btn = QPushButton("📷  Камера")
        self.cam_btn.setStyleSheet(self._btn("#27ae60"))
        self.cam_btn.clicked.connect(self._camera)
        row.addWidget(self.file_btn); row.addWidget(self.cam_btn); row.addStretch()
        layout.addLayout(row)

        # Лента фото
        sc = QScrollArea()
        sc.setFixedHeight(150)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setWidgetResizable(True)
        sc.setStyleSheet("background:#111;border:1px solid #2a2a2a;border-radius:8px;")
        self._tc = QWidget()
        self._tl = QHBoxLayout(self._tc)
        self._tl.setContentsMargins(8,8,8,8); self._tl.setSpacing(8)
        self._tl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._empty = QLabel("Нет добавленных фото")
        self._empty.setStyleSheet("color:#444;font-size:13px;")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tl.addWidget(self._empty)
        sc.setWidget(self._tc)
        layout.addWidget(sc)

        self._cnt = QLabel("0 фото добавлено")
        self._cnt.setStyleSheet("color:#666;font-size:12px;")
        layout.addWidget(self._cnt)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setStyleSheet("color:#2a2a2a;")
        layout.addWidget(sep)

        # ✅ Языки строятся с пустым списком — заполнятся после _on_tess_ready()
        self._lang_sel = LangSelectorWidget([], self)
        self._lang_sel.selection_changed.connect(self._upd_btn)
        self._lang_sel.install_requested.connect(self._install_langs)
        self._lang_sel.refresh_requested.connect(self._refresh_langs)
        layout.addWidget(self._lang_sel)

        # Статус — сразу показывает "Проверяю Tesseract…"
        self._ocr_status = QLabel("🔍 Проверяю Tesseract…")
        self._ocr_status.setStyleSheet("color:#888; font-size:12px;")
        self._ocr_status.setWordWrap(True)
        layout.addWidget(self._ocr_status)

        layout.addStretch()
        brow = QHBoxLayout()
        skip = QPushButton("Пропустить")
        skip.setStyleSheet("QPushButton{background:#2a2a2a;color:#888;border:1px solid #3a3a3a;border-radius:8px;padding:8px 24px;}QPushButton:hover{background:#333;color:#ccc;}")
        skip.clicked.connect(self.reject)
        self.ok_btn = QPushButton("🔍  Распознать текст")
        self.ok_btn.setEnabled(False)
        self.ok_btn.setStyleSheet("QPushButton{background:#4a9eff;color:white;border:none;border-radius:8px;padding:8px 28px;font-weight:bold;}QPushButton:hover{background:#5aadff;}QPushButton:disabled{background:#1a3a5a;color:#555;}")
        self.ok_btn.clicked.connect(self._start_ocr)
        brow.addWidget(skip); brow.addStretch(); brow.addWidget(self.ok_btn)
        layout.addLayout(brow)

    # ── Фото ─────────────────────────────────────────────────────────────

    def _pick(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Выбери фотографии", "",
            "Изображения (*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp)")
        for p in paths: self._add(p)

    def _camera(self):
        try:
            import cv2  # noqa
        except ImportError:
            QMessageBox.information(self, "Камера", "pip install opencv-python")
            return
        d = CameraDialog(self)
        d.photo_taken.connect(self._add)
        d.exec()

    def _add(self, path: str):
        if path in self._photos: return
        self._photos.append(path)
        if len(self._photos) == 1:
            self._empty.setVisible(False)
        t = PhotoThumbnail(path, self._tc)
        t.removed.connect(self._remove)
        self._tl.addWidget(t)
        self._upd_count()

    def _remove(self, path: str):
        if path not in self._photos: return
        self._photos.remove(path)
        for i in range(self._tl.count()):
            w = self._tl.itemAt(i).widget()
            if isinstance(w, PhotoThumbnail) and w.path == path:
                w.setParent(None); break
        if not self._photos:
            self._empty.setVisible(True)
        self._upd_count()

    def _upd_count(self):
        n = len(self._photos)
        self._cnt.setText(f"{n} фото добавлено" if n else "0 фото добавлено")
        self._upd_btn()

    def _upd_btn(self):
        # Разрешаем OCR если: есть фото + выбраны языки + (tesseract найден ИЛИ есть tessdata)
        self.ok_btn.setEnabled(
            bool(self._photos) and bool(self._lang_sel.get_selected_langs()) and
            (self._tess_ok or bool(self._installed))
        )

    # ── Языки ─────────────────────────────────────────────────────────────

    def _refresh_langs(self):
        """Перечитывает tessdata в фоне — не блокирует UI."""
        self._lang_sel.set_checking(True)     # ← блокируем на время
        self._ocr_status.setStyleSheet("color:#888; font-size:12px;")
        self._ocr_status.setText("🔄 Ищу Tesseract и языковые пакеты…")
        self._init_thread = TesseractInitThread(self)
        self._init_thread.ready.connect(self._on_tess_ready)
        self._init_thread.start()

    def _install_langs(self):
        tl = _get_tl()
        missing = [c for c in DEFAULT_LANGS if c not in self._installed]
        dlg = tl.LangInstallDialog(preselect=missing, parent=self)
        dlg.langs_changed.connect(self._refresh_langs)
        dlg.exec()

    # ── OCR ───────────────────────────────────────────────────────────────

    def _start_ocr(self):
        langs = self._lang_sel.get_selected_langs()
        if not langs: return
        self.ok_btn.setEnabled(False)
        self.file_btn.setEnabled(False)
        self.cam_btn.setEnabled(False)
        self._ocr_status.setText(f"⏳ Распознаю [{'+'.join(langs)}]…")
        self._ocr_thread = OcrThread(list(self._photos), langs)
        self._ocr_thread.progress.connect(lambda c,t,m: self._ocr_status.setText(f"⏳ {m}"))
        self._ocr_thread.finished.connect(self._ocr_done)
        self._ocr_thread.error.connect(self._ocr_error)
        self._ocr_thread.start()

    def _ocr_done(self, text: str):
        self._ocr_text = text
        langs = "+".join(self._lang_sel.get_selected_langs())
        if text:
            self._ocr_status.setText(
                f"✅ Готово · {len(self._photos)} фото · {len(text)} симв. · [{langs}]")
        else:
            self._ocr_status.setText("⚠️ Текст не найден")
        self.accept()

    def _ocr_error(self, msg: str):
        self._ocr_status.setText(f"❌ {msg}")
        self.ok_btn.setEnabled(True)
        self.file_btn.setEnabled(True)
        self.cam_btn.setEnabled(True)

    def get_ocr_text(self) -> str:
        return self._ocr_text

    @staticmethod
    def _btn(color: str) -> str:
        return (f"QPushButton{{background:{color};color:white;border:none;"
                f"border-radius:8px;padding:8px 20px;}}"
                f"QPushButton:hover{{background:{color}cc;}}")
