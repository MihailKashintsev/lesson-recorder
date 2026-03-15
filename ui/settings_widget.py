"""
ПАТЧ для ui/settings_widget.py
Исправляет три проблемы:
  1. PyAudioWPatch показывается на Mac — добавляем поле "platforms": ["win32"]
  2. QThread краш — не удаляем ссылку пока поток жив
  3. _install_missing пытается ставить Windows-пакеты на Mac

КАК ПРИМЕНИТЬ:
  Замени в settings_widget.py указанные блоки кода на исправленные версии.
  Ищи строки по первому слову/символу блока — они уникальны.
"""

# ══════════════════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 1:  PyAudioWPatch — добавить поле "platforms"
# Найди в PACKAGES_INFO блок с "PyAudioWPatch" и замени на:
# ══════════════════════════════════════════════════════════════════════════════

PYAUDIO_PATCH = """
    {
        "import_name": "pyaudiowpatch",
        "pip_name":    "PyAudioWPatch",
        "label":       "PyAudioWPatch",
        "desc":        "Запись системного звука (WASAPI loopback, только Windows)",
        "used_for":    "🖥 Системный звук",
        "required":    False,
<<<<<<< HEAD
        "platforms":   ["win32"],
=======
        "platforms":   ["win32"],           # ← ТОЛЬКО Windows, скрывать на Mac/Linux
>>>>>>> 588ac9d (-)
        "github_url":  "https://github.com/s0d3s/PyAudioWPatch",
    },
"""

# ══════════════════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 2:  _fill_pkg_rows — фильтрация по платформе
# Найди метод _fill_pkg_rows и замени начало цикла for pkg in PACKAGES_INFO:
# ══════════════════════════════════════════════════════════════════════════════

FILL_ROWS_PATCH = """
    def _fill_pkg_rows(self, c: dict | None = None):
        if c is None:
            c = get_colors(self._theme)
        while self._pkg_vbox.count():
            item = self._pkg_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._pkg_rows.clear()

        # Фильтруем пакеты по текущей платформе
        visible_packages = [
            pkg for pkg in PACKAGES_INFO
            if not pkg.get("platforms") or sys.platform in pkg["platforms"]
        ]

<<<<<<< HEAD
        # Сначала рисуем все строки с "🔍 проверяю…"
=======
>>>>>>> 588ac9d (-)
        for pkg in visible_packages:
            row_w = self._build_pkg_row(pkg, c, checking=True)
            self._pkg_vbox.addWidget(row_w)

        self._start_pkg_check()
"""

# ══════════════════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 3:  _start_pkg_check — передавать только видимые пакеты
# Замени метод _start_pkg_check:
# ══════════════════════════════════════════════════════════════════════════════

START_PKG_CHECK_PATCH = """
    def _start_pkg_check(self):
<<<<<<< HEAD
        """Запускает PkgCheckThread для видимых пакетов параллельно."""
        _pip_show_cache.clear()
=======
        _pip_show_cache.clear()
        # Проверяем только те пакеты, строки которых реально созданы
>>>>>>> 588ac9d (-)
        pip_names = list(self._pkg_rows.keys())
        if not pip_names:
            return
        t = PkgCheckThread(pip_names)
        t.pkg_checked.connect(self._on_pkg_checked)
        t.start()
        self._pkg_check_thread = t
"""

# ══════════════════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 4:  _install_missing — фильтрация по платформе
# Замени метод _install_missing:
# ══════════════════════════════════════════════════════════════════════════════

INSTALL_MISSING_PATCH = """
    def _install_missing(self):
        for pkg in PACKAGES_INFO:
<<<<<<< HEAD
=======
            # Пропускаем пакеты не для этой платформы
>>>>>>> 588ac9d (-)
            if pkg.get("platforms") and sys.platform not in pkg["platforms"]:
                continue
            if not _is_package_installed(pkg["pip_name"], pkg["import_name"]):
                self._install_by_name(pkg["pip_name"])
"""

# ══════════════════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 5 (ГЛАВНОЕ): _on_pip_done — краш QThread
# Причина краша: self._pip_threads.pop(pip_name, None) удаляет последнюю
# ссылку на QThread пока он ещё работает → Python GC его уничтожает →
# Qt вызывает QMessageLogger::fatal → SIGABRT
#
# Замени метод _on_pip_done на:
# ══════════════════════════════════════════════════════════════════════════════

ON_PIP_DONE_PATCH = """
    def _on_pip_done(self, pip_name: str, success: bool, output: str):
<<<<<<< HEAD
        # Не удаляем поток сразу — ждём QThread.finished чтобы избежать SIGABRT
        t = self._pip_threads.get(pip_name)
        if t:
=======
        # ❌ НЕЛЬЗЯ: self._pip_threads.pop(pip_name, None)
        # Qt требует что QThread дожил до wait() перед удалением.
        # Вместо pop() — помечаем для отложенной очистки через finished-сигнал.
        t = self._pip_threads.get(pip_name)
        if t:
            # Подключаем однократный слот очистки к built-in QThread.finished
>>>>>>> 588ac9d (-)
            try:
                t.finished.disconnect()
            except Exception:
                pass
            t.finished.connect(lambda pn=pip_name: self._pip_threads.pop(pn, None))
<<<<<<< HEAD
=======

>>>>>>> 588ac9d (-)
        row = self._pkg_rows.get(pip_name)
        if not row:
            return

        c = get_colors(self._theme)

        if not success:
            row["btn"].setEnabled(True)
            row["btn"].setText("🗑 Удалить" if row.get("installed") else "⬇ Установить")
            row["action_lbl"].setText("❌ Ошибка")
            row["action_lbl"].setToolTip(output[:300])
            self._show_pip_log(pip_name, success=False, output=output)
            return

        _pip_show_cache.pop(pip_name, None)
        row["action_lbl"].setText("🔍 проверяю…")
        row["status_lbl"].setText("🔍")
        row["btn"].setEnabled(False)
        row["btn"].setText("🔍")

        if "path_lbl" in row:
            row["path_lbl"].setText("🔍 проверяю…")
            row["path_lbl"].setStyleSheet(f"color:{c['text_muted']};font-size:10px;")

        recheck_key = f"__recheck_{pip_name}"
        t2 = PkgCheckThread([pip_name])
        t2.pkg_checked.connect(self._on_pkg_checked)
        t2.pkg_checked.connect(lambda pn, inst, path: self._after_recheck(pn))
        # Очистка после завершения через finished — не через pop в _after_recheck
        t2.finished.connect(lambda: self._pip_threads.pop(recheck_key, None))
        t2.start()
        self._pip_threads[recheck_key] = t2
"""

# ══════════════════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 6:  _after_recheck — убрать лишний pop (он теперь в finished)
# Замени метод _after_recheck на:
# ══════════════════════════════════════════════════════════════════════════════

AFTER_RECHECK_PATCH = """
    def _after_recheck(self, pip_name: str):
        row = self._pkg_rows.get(pip_name)
        if row:
            row["action_lbl"].setText("✅ Готово")
<<<<<<< HEAD

    def _show_pip_log(self, pip_name: str, success: bool, output: str):
        """Показывает диалог с полным выводом pip."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel
        c = get_colors(self._theme)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"pip {'install' if not success else 'output'} — {pip_name}")
        dlg.setMinimumSize(560, 400)
        dlg.setStyleSheet(f"QDialog{{background:{c['bg_panel']};color:{c['text']};}}")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        status_text = "❌ Ошибка установки" if not success else "✅ Успешно"
        lbl = QLabel(f"{status_text} — {pip_name}")
        lbl.setStyleSheet(
            f"color:{'#f44336' if not success else '#4caf50'};"
            "font-size:13px;font-weight:600;")
        lay.addWidget(lbl)

        hint = QLabel("Скопируй и запусти команду вручную в терминале:")
        hint.setStyleSheet(f"color:{c['text_muted']};font-size:11px;")
        lay.addWidget(hint)

        cmd_lbl = QLabel(f"pip install {pip_name}")
        cmd_lbl.setStyleSheet(
            f"color:{c['accent_blue']};font-size:12px;font-weight:600;"
            f"background:{c['bg_input']};border-radius:5px;padding:6px 10px;")
        cmd_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(cmd_lbl)

        log = QTextEdit()
        log.setReadOnly(True)
        log.setPlainText(output or "(нет вывода)")
        log.setStyleSheet(
            f"QTextEdit{{background:#0d1117;color:#e6edf3;"
            f"border:1px solid {c['border']};border-radius:6px;"
            f"font-family:Consolas,monospace;font-size:11px;padding:8px;}}")
        lay.addWidget(log, stretch=1)

        from PyQt6.QtWidgets import QHBoxLayout
        btn_row = QHBoxLayout()
        btn_copy = QPushButton("📋  Скопировать лог")
        btn_copy.setStyleSheet(
            f"QPushButton{{background:{c['bg_input']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:6px;padding:6px 14px;}}"
            f"QPushButton:hover{{background:{c['bg_hover']};}}")
        btn_copy.clicked.connect(
            lambda: __import__("PyQt6.QtWidgets", fromlist=["QApplication"])
            .QApplication.clipboard().setText(output))
        btn_row.addWidget(btn_copy)
        btn_row.addStretch()
        btn_close = QPushButton("Закрыть")
        btn_close.setStyleSheet(
            f"QPushButton{{background:{c['accent_blue']};color:#fff;"
            f"border:none;border-radius:6px;padding:6px 18px;}}"
            f"QPushButton:hover{{background:{c['accent_blue']}cc;}}")
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)

        dlg.exec()

    # ── Сохранение ────────────────────────────────────────────────────────

    def _save(self):
        provider_id = self.combo_provider.currentData()
        src_keys = ["mic", "system", "both"]

        mic_device_index = self.combo_mic_device.currentData()

        self.settings.update({
            "audio_source": src_keys[self.combo_source.currentIndex()],
            "mic_device_index": mic_device_index,
            "whisper_model": self.combo_whisper_model.currentText(),
            "language": self.combo_lang.currentData(),
            "ai_provider": provider_id,
            "ai_api_key": self.edit_api_key.text().strip(),
            "ai_model": self._get_current_model(),
            "ai_custom_url": self.edit_custom_url.text().strip(),
            "ai_custom_model": self.edit_custom_model.text().strip(),
            "theme": self._theme,
        })
        save_settings(self.settings)

        # ✅ НЕТ перезапуска приложения — только инфо
        c = get_colors(self._theme)
        msg = QMessageBox(self)
        msg.setWindowTitle("Настройки сохранены")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("✅ Настройки успешно сохранены!")
        msg.setStyleSheet(f"QMessageBox {{ background: {c['bg_card'] if 'bg_card' in c else c['bg_panel']}; color: {c['text']}; }}")
        msg.exec()

    def get_settings(self) -> dict:
        return load_settings()

    # ── Стили ─────────────────────────────────────────────────────────────

    def _secondary_btn_style(self, c: dict) -> str:
        return f"""
            QPushButton {{
                background: {c['bg_input']}; color: {c['text']};
                border: 1px solid {c['border']}; border-radius: 6px;
                padding: 6px 16px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {c['bg_hover']}; color: {c['text']}; }}
        """

    def _link_btn_style(self, c: dict) -> str:
        return f"""
            QPushButton {{
                background: transparent; color: {c['accent_blue']};
                border: 1px solid {c['accent_blue']}; border-radius: 6px;
                padding: 6px 14px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {c['bg_selected']}; }}
        """
=======
        # pop теперь делается в t2.finished.connect выше — здесь не нужен
"""
>>>>>>> 588ac9d (-)
