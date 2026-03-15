"""
ПАТЧ для core/tesseract_langs.py
Исправляет:
  1. find_tesseract_cmd — добавить пути для Mac (Homebrew)
  2. TesseractInstallerThread — кросс-платформенная установка
  3. TesseractTab — правильные инструкции для Mac/Linux

КАК ПРИМЕНИТЬ:
  Замени в tesseract_langs.py указанные блоки на исправленные версии.
"""

# ══════════════════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 1: _find_tesseract_cmd_uncached — добавить Mac/Linux пути
# Замени всю функцию _find_tesseract_cmd_uncached на:
# ══════════════════════════════════════════════════════════════════════════════

FIND_TESSERACT_PATCH = """
def _find_tesseract_cmd_uncached() -> str | None:
    # 1. Фиксированные пути Windows — мгновенно
    if sys.platform == "win32":
        for p in [
<<<<<<< HEAD
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Tesseract-OCR\tesseract.exe",
            r"C:\Tesseract\tesseract.exe",
            r"C:\tools\Tesseract-OCR\tesseract.exe",
=======
            r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
            r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
            r"C:\\Tesseract-OCR\\tesseract.exe",
            r"C:\\Tesseract\\tesseract.exe",
            r"C:\\tools\\Tesseract-OCR\\tesseract.exe",
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
        ]:
            if Path(p).exists():
                return p

<<<<<<< HEAD
    # 2. Homebrew macOS (до PATH — шебанги могут не обновить PATH)
    if sys.platform == "darwin":
        for p in [
            "/opt/homebrew/bin/tesseract",   # Apple Silicon
            "/usr/local/bin/tesseract",       # Intel Mac
=======
    # 2. Homebrew (macOS) — до PATH, т.к. шебанги могут не обновить PATH
    if sys.platform == "darwin":
        for p in [
            "/opt/homebrew/bin/tesseract",    # Apple Silicon
            "/usr/local/bin/tesseract",        # Intel Mac
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
        ]:
            if Path(p).exists():
                return p

<<<<<<< HEAD
    # 3. PATH — мгновенно (все платформы)
=======
    # 3. PATH — мгновенно (работает на всех платформах)
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
    found = shutil.which("tesseract")
    if found:
        return found

    # 4. Linux стандартные пути
    if sys.platform.startswith("linux"):
<<<<<<< HEAD
        for p in ["/usr/bin/tesseract", "/usr/local/bin/tesseract"]:
            if Path(p).exists():
                return p

    # 5. Реестр Windows — быстро
    if sys.platform != "win32":
        return None
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
=======
        for p in [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
        ]:
            if Path(p).exists():
                return p
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)

    # 5. Реестр Windows
    if sys.platform == "win32":
        try:
            import winreg
            for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                for sub in [r"SOFTWARE\\Tesseract-OCR",
                            r"SOFTWARE\\WOW6432Node\\Tesseract-OCR"]:
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

    # 6. where/which как последний шанс
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

    return None
"""

# ══════════════════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 2: TesseractInstallerThread — кросс-платформенный
# Замени весь класс TesseractInstallerThread на:
# ══════════════════════════════════════════════════════════════════════════════

INSTALLER_THREAD_PATCH = """
class TesseractInstallerThread(QThread):
    progress = pyqtSignal(int)
    status   = pyqtSignal(str)
    finished = pyqtSignal(str)   # путь к установщику (Windows) или "" (Mac/Linux)
    error    = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        if sys.platform == "darwin":
            self._install_mac()
        elif sys.platform.startswith("linux"):
            self._install_linux()
        else:
            self._install_windows()

    def _install_mac(self):
<<<<<<< HEAD
        brew = shutil.which("brew")
        if not brew:
            self.error.emit(
                "Homebrew не найден.\n\n"
                "Установи Homebrew: https://brew.sh\n"
                "Затем выполни: brew install tesseract"
=======
        \"\"\"Устанавливает Tesseract через Homebrew на macOS.\"\"\"
        import shutil
        brew = shutil.which("brew")
        if not brew:
            self.error.emit(
                "Homebrew не найден.\\n\\n"
                "Установи Homebrew, затем выполни в терминале:\\n"
                "  brew install tesseract"
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
            )
            return
        self.status.emit("Устанавливаю Tesseract через Homebrew…")
        self.progress.emit(10)
        try:
<<<<<<< HEAD
            import subprocess as _sp
            proc = _sp.Popen([brew, "install", "tesseract"],
                             stdout=_sp.PIPE, stderr=_sp.STDOUT, text=True)
            for line in proc.stdout:
                if self._cancelled:
                    proc.kill(); return
=======
            proc = subprocess.Popen(
                [brew, "install", "tesseract"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True,
            )
            for line in proc.stdout:
                if self._cancelled:
                    proc.kill()
                    return
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
                self.status.emit(line.strip()[:80])
            proc.wait()
            if proc.returncode == 0:
                self.progress.emit(100)
                self.finished.emit("")
            else:
<<<<<<< HEAD
                self.error.emit(f"Homebrew вернул код {proc.returncode}\nПопробуй: brew install tesseract")
=======
                self.error.emit(
                    f"Homebrew вернул код {proc.returncode}.\\n"
                    "Попробуй вручную: brew install tesseract"
                )
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
        except Exception as e:
            self.error.emit(str(e))

    def _install_linux(self):
<<<<<<< HEAD
=======
        \"\"\"Устанавливает Tesseract через системный менеджер пакетов.\"\"\"
        import shutil
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
        pkg_managers = [
            (shutil.which("apt-get"), ["sudo", "apt-get", "install", "-y", "tesseract-ocr"]),
            (shutil.which("dnf"),     ["sudo", "dnf", "install", "-y", "tesseract"]),
            (shutil.which("pacman"),  ["sudo", "pacman", "-S", "--noconfirm", "tesseract"]),
<<<<<<< HEAD
        ]
        import subprocess as _sp
=======
            (shutil.which("zypper"),  ["sudo", "zypper", "install", "-y", "tesseract-ocr"]),
        ]
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
        for mgr, cmd in pkg_managers:
            if mgr:
                self.status.emit(f"Устанавливаю через {Path(mgr).name}…")
                try:
<<<<<<< HEAD
                    proc = _sp.Popen(cmd, stdout=_sp.PIPE, stderr=_sp.STDOUT, text=True)
                    for line in proc.stdout:
                        if self._cancelled:
                            proc.kill(); return
                        self.status.emit(line.strip()[:80])
                    proc.wait()
                    if proc.returncode == 0:
                        self.progress.emit(100); self.finished.emit("")
=======
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                    )
                    for line in proc.stdout:
                        if self._cancelled:
                            proc.kill()
                            return
                        self.status.emit(line.strip()[:80])
                    proc.wait()
                    if proc.returncode == 0:
                        self.progress.emit(100)
                        self.finished.emit("")
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
                    else:
                        self.error.emit(f"Менеджер пакетов вернул код {proc.returncode}")
                except Exception as e:
                    self.error.emit(str(e))
                return
<<<<<<< HEAD
        self.error.emit("Не удалось определить менеджер пакетов.\nsudo apt install tesseract-ocr")

    def _install_windows(self):
=======
        self.error.emit(
            "Не удалось определить менеджер пакетов.\\n"
            "Установи вручную: sudo apt install tesseract-ocr"
        )

    def _install_windows(self):
        \"\"\"Скачивает и запускает установщик для Windows.\"\"\"
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
        import requests
        try:
            self.status.emit("Подключаюсь к серверу…")
            tmp_dir = tempfile.mkdtemp(prefix="lr_tess_")
            dest    = Path(tmp_dir) / "tesseract-installer.exe"
            tmp     = dest.with_suffix(".tmp")
            r = requests.get(TESSERACT_INSTALLER_URL, stream=True, timeout=30)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            self.status.emit(f"Скачиваю Tesseract {TESSERACT_INSTALLER_VERSION}…")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if self._cancelled:
                        tmp.unlink(missing_ok=True); return
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
"""

# ══════════════════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 3: TesseractTab._build — кросс-платформенный текст
# Замени блок с desc = QLabel(...) (описание) и note = QLabel(...) (подсказка),
# а также dl_btn текст. Найди в _build после добавления карточки статуса:
# ══════════════════════════════════════════════════════════════════════════════

TESSERACT_TAB_BUILD_PATCH = """
        # Описание — зависит от платформы
        if sys.platform == "darwin":
            desc_text = (
                "<b>Tesseract OCR</b> — бесплатный движок распознавания текста (Google).<br>"
                "Без него функция «Фото → Текст» не работает.<br><br>"
                "Будет установлен через <b>Homebrew</b> командой:<br>"
                "<code style='background:#1a1a1a;padding:2px 6px;border-radius:4px;'>"
                "brew install tesseract</code>"
            )
            btn_text  = "🍺  Установить через Homebrew"
            note_text = "💡 Homebrew установит tesseract и все зависимости автоматически."
        elif sys.platform.startswith("linux"):
            desc_text = (
                "<b>Tesseract OCR</b> — бесплатный движок распознавания текста (Google).<br>"
                "Без него функция «Фото → Текст» не работает.<br><br>"
                "Будет установлен через системный менеджер пакетов<br>"
                "(apt, dnf, pacman — определяется автоматически)."
            )
            btn_text  = "📦  Установить Tesseract"
            note_text = "💡 Потребуется пароль sudo для установки системного пакета."
        else:
            desc_text = (
                "<b>Tesseract OCR</b> — бесплатный движок распознавания текста (Google).<br>"
                "Без него функция «Фото → Текст» не работает.<br><br>"
                f"Будет скачан установщик <b>v{TESSERACT_INSTALLER_VERSION}</b> (~48 МБ) "
                "с официального репозитория <b>UB-Mannheim</b>."
            )
            btn_text  = "⬇  Скачать и установить Tesseract"
            note_text = (
                "💡 При установке рекомендуется отметить <b>«Additional language data»</b> — "
                "тогда языки скачивать отдельно не нужно."
            )
"""

# ══════════════════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 4: TesseractTab._on_downloaded — Mac не запускает .exe
# Замени метод _on_downloaded на:
# ══════════════════════════════════════════════════════════════════════════════

ON_DOWNLOADED_PATCH = """
    def _on_downloaded(self, exe_path: str):
        self.pbar.setValue(100)
        self.cancel_btn.setVisible(False)
<<<<<<< HEAD
        global _tesseract_cmd_cache
        _tesseract_cmd_cache = False
        if not exe_path:
            # Mac/Linux — установка завершена внутри потока
            self.status_lbl.setText("✅ Tesseract установлен! Перезапустите приложение.")
            self.installed.emit()
            self.dl_btn.setEnabled(True)
            return
        # Windows — запускаем скачанный .exe
=======

        if not exe_path:
            # Mac/Linux — установка уже завершена внутри потока
            self.status_lbl.setText(
                "✅ Tesseract установлен! Перезапустите приложение."
            )
            global _tesseract_cmd_cache
            _tesseract_cmd_cache = False
            self.installed.emit()
            self.dl_btn.setEnabled(True)
            return

        # Windows — запускаем скачанный .exe установщик
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
        try:
            subprocess.Popen([exe_path], shell=True)
            self.status_lbl.setText(
                "✅ Установщик запущен. После установки перезапусти приложение."
            )
<<<<<<< HEAD
=======
            global _tesseract_cmd_cache
            _tesseract_cmd_cache = False
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
            self.installed.emit()
        except Exception as e:
            self.status_lbl.setText(f"❌ Не удалось запустить: {e}")
        self.dl_btn.setEnabled(True)
<<<<<<< HEAD

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
=======
"""
>>>>>>> 23bcb08 (fix: QThread crash on mac, hide PyAudioWPatch on non-windows, cross-platform Tesseract installer)
