"""
О проекте — страница с информацией о приложении, команде и ссылками.
"""
import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QCursor

from ui.theme import get_colors


# ── Ссылки проекта ────────────────────────────────────────────────────────────
LINKS = [
    {
        "icon":  "✈",
        "label": "Telegram канал",
        "sub":   "@rendergm",
        "url":   "https://t.me/rendergm",
        "color": "#2AABEE",
    },
    {
        "icon":  "🌐",
        "label": "Сайт",
        "sub":   "rendergames.tilda.ws",
        "url":   "https://rendergames.tilda.ws/",
        "color": "#58a6ff",
    },
    {
        "icon":  "💛",
        "label": "Поддержать на Boosty",
        "sub":   "boosty.to/rendergamesru",
        "url":   "https://boosty.to/rendergamesru/purchase/3242287?ssource=DIRECT&share=subscription_link",
        "color": "#f7931a",
    },
]


# ── Получить дату последнего обновления (через тот же механизм что updater.py) ──
class UpdateCheckerThread(QThread):
    result = pyqtSignal(str)   # "v1.4.0  ·  25 февраля 2025" или ""

    def run(self):
        try:
            # Переиспользуем готовую функцию из updater — одна точка истины
            from core.updater import _get_latest_release
            release = _get_latest_release()
            if not release:
                self.result.emit("")
                return

            tag  = release.get("tag_name", "")
            date = release.get("published_at", "")[:10]  # "2025-02-25"
            if date:
                y, m, d = date.split("-")
                months = ["", "января","февраля","марта","апреля","мая",
                          "июня","июля","августа","сентября","октября",
                          "ноября","декабря"]
                date_ru = f"{int(d)} {months[int(m)]} {y}"
                self.result.emit(f"{tag}  ·  {date_ru}")
                return
        except Exception:
            pass
        self.result.emit("")


# ── Карточка-ссылка ───────────────────────────────────────────────────────────
class LinkCard(QWidget):
    def __init__(self, icon: str, label: str, sub: str,
                 url: str, color: str, theme: str, parent=None):
        super().__init__(parent)
        self._url   = url
        self._color = color
        self._theme = theme
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._build(icon, label, sub, color, theme)
        self._setup_hover()

    def _build(self, icon, label, sub, color, theme):
        c   = get_colors(theme)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(14)

        # Иконка
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            f"font-size:22px; color:{color}; background:transparent;")
        icon_lbl.setFixedWidth(32)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon_lbl)

        # Текст
        txt = QVBoxLayout()
        txt.setSpacing(2)
        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            f"font-size:13px; font-weight:600; color:{c['text']};"
            "background:transparent;")
        sub_lbl  = QLabel(sub)
        sub_lbl.setStyleSheet(
            f"font-size:11px; color:{c['text_muted']}; background:transparent;")
        txt.addWidget(name_lbl)
        txt.addWidget(sub_lbl)
        lay.addLayout(txt)

        lay.addStretch()

        # Стрелка
        arr = QLabel("→")
        arr.setStyleSheet(
            f"font-size:16px; color:{c['text_dim']}; background:transparent;")
        lay.addWidget(arr)

        self._set_bg(False)

    def _set_bg(self, hovered: bool):
        c = get_colors(self._theme)
        bg = c["bg_hover"] if hovered else c["bg_panel"]
        self.setStyleSheet(f"""
            LinkCard, QWidget {{
                background: {bg};
                border: 1px solid {"" + self._color + "55" if hovered else c["border"]};
                border-radius: 12px;
            }}
        """)

    def _setup_hover(self):
        # Анимация через enterEvent/leaveEvent — QPropertyAnimation на цвет
        # не работает для border, поэтому просто меняем stylesheet
        pass

    def enterEvent(self, e):
        self._set_bg(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._set_bg(False)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            webbrowser.open(self._url)
        super().mousePressEvent(e)

    def apply_theme(self, theme: str):
        self._theme = theme
        self._set_bg(False)


# ── Главный виджет ────────────────────────────────────────────────────────────
class AboutWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme  = "dark"
        self._thread = None
        self._update_lbl: QLabel | None = None
        self._link_cards: list[LinkCard] = []
        self._build_ui()
        self._fetch_update_info()

    def apply_theme(self, theme: str):
        self._theme = theme
        self._refresh_styles()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        c = get_colors(self._theme)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        self._header = QWidget()
        self._header.setObjectName("aboutHeader")
        self._header.setFixedHeight(56)
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(28, 0, 28, 0)
        self._title_lbl = QLabel("О проекте")
        self._title_lbl.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{c['text']};")
        hl.addWidget(self._title_lbl)
        hl.addStretch()
        root.addWidget(self._header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("aboutSep")
        sep.setStyleSheet(f"color:{c['border']};")
        self._sep = sep
        root.addWidget(sep)

        # ── Scroll area ───────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(28, 28, 28, 40)
        lay.setSpacing(24)
        self._inner_layout = lay

        # ── Hero блок (лого + название) ───────────────────────────────────────
        hero = QWidget()
        hero.setObjectName("aboutHero")
        hero.setStyleSheet(f"""
            QWidget#aboutHero {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #1a2744, stop:1 #0d1117);
                border: 1px solid #30363d;
                border-radius: 16px;
            }}
        """)
        self._hero = hero
        hl2 = QVBoxLayout(hero)
        hl2.setContentsMargins(28, 28, 28, 28)
        hl2.setSpacing(6)

        logo_lbl = QLabel("🎙")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setStyleSheet("font-size:48px; background:transparent;")
        hl2.addWidget(logo_lbl)

        app_name = QLabel("LessonRecorder")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_name.setStyleSheet(
            "font-size:22px; font-weight:700; color:#e6edf3; background:transparent;")
        hl2.addWidget(app_name)

        app_desc = QLabel("Запись уроков · Транскрипция · AI-конспект")
        app_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_desc.setStyleSheet(
            "font-size:12px; color:#8b949e; background:transparent; margin-top:2px;")
        hl2.addWidget(app_desc)

        try:
            from version import __version__
        except ImportError:
            __version__ = "dev"

        self._ver_lbl = QLabel(f"Версия {__version__}")
        self._ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ver_lbl.setStyleSheet(
            "font-size:11px; color:#484f58; background:transparent; margin-top:4px;")
        hl2.addWidget(self._ver_lbl)

        lay.addWidget(hero)

        # ── Последнее обновление ──────────────────────────────────────────────
        self._update_card = self._make_info_card()
        upd_lay = QHBoxLayout(self._update_card)
        upd_lay.setContentsMargins(18, 14, 18, 14)
        upd_lay.setSpacing(12)

        upd_icon = QLabel("🔄")
        upd_icon.setStyleSheet("font-size:18px; background:transparent;")
        upd_lay.addWidget(upd_icon)

        upd_txt = QVBoxLayout()
        upd_txt.setSpacing(2)
        upd_title = QLabel("Последнее обновление")
        upd_title.setStyleSheet(
            f"font-size:12px; font-weight:600; color:{c['text_muted']};"
            "background:transparent; text-transform:uppercase; letter-spacing:0.5px;")
        self._upd_title = upd_title
        self._update_lbl = QLabel("Загружаю…")
        self._update_lbl.setStyleSheet(
            f"font-size:14px; font-weight:600; color:{c['text']}; background:transparent;")
        upd_txt.addWidget(upd_title)
        upd_txt.addWidget(self._update_lbl)
        upd_lay.addLayout(upd_txt)
        upd_lay.addStretch()
        lay.addWidget(self._update_card)

        # ── Секция: Команда ───────────────────────────────────────────────────
        lay.addWidget(self._section_label("Команда"))

        team_card = self._make_info_card()
        self._team_card = team_card
        tl = QVBoxLayout(team_card)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)

        members = [
            ("👨‍💻", "MihailKashintsev", "Разработчик"),
            ("🎮", "RENDERGAMES",      "Команда разработки"),
        ]
        for i, (icon, name, role) in enumerate(members):
            row = QWidget()
            row.setStyleSheet("background:transparent;")
            rl2 = QHBoxLayout(row)
            rl2.setContentsMargins(18, 12, 18, 12)
            rl2.setSpacing(14)

            ic = QLabel(icon)
            ic.setStyleSheet("font-size:20px; background:transparent;")
            ic.setFixedWidth(32)
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rl2.addWidget(ic)

            info = QVBoxLayout()
            info.setSpacing(1)
            nm = QLabel(name)
            nm.setStyleSheet(
                f"font-size:14px; font-weight:700; color:{c['text']}; background:transparent;")
            ro = QLabel(role)
            ro.setStyleSheet(
                f"font-size:11px; color:{c['text_muted']}; background:transparent;")
            info.addWidget(nm)
            info.addWidget(ro)
            rl2.addLayout(info)
            rl2.addStretch()
            tl.addWidget(row)

            if i < len(members) - 1:
                div = QFrame()
                div.setFrameShape(QFrame.Shape.HLine)
                div.setStyleSheet(f"color:{c['border']}; margin-left:18px;")
                tl.addWidget(div)

        lay.addWidget(team_card)

        # ── Секция: Ссылки ────────────────────────────────────────────────────
        lay.addWidget(self._section_label("Найти нас"))

        for link in LINKS:
            card = LinkCard(
                icon=link["icon"], label=link["label"],
                sub=link["sub"],   url=link["url"],
                color=link["color"], theme=self._theme,
            )
            self._link_cards.append(card)
            lay.addWidget(card)

        lay.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_info_card(self) -> QWidget:
        c = get_colors(self._theme)
        w = QWidget()
        w.setStyleSheet(f"""
            QWidget {{
                background: {c['bg_panel']};
                border: 1px solid {c['border']};
                border-radius: 12px;
            }}
        """)
        return w

    def _section_label(self, text: str) -> QLabel:
        c   = get_colors(self._theme)
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size:10px; font-weight:700; color:{c['text_dim']};"
            "letter-spacing:1.2px; background:transparent; padding-left:2px;")
        return lbl

    # ── Обновление через GitHub API ───────────────────────────────────────────

    def _fetch_update_info(self):
        self._thread = UpdateCheckerThread()
        self._thread.result.connect(self._on_update_result)
        self._thread.start()

    def _on_update_result(self, text: str):
        if self._update_lbl:
            if text:
                self._update_lbl.setText(text)
            else:
                self._update_lbl.setText("Нет данных")
                self._update_lbl.setStyleSheet(
                    "font-size:13px; color:#484f58; background:transparent;")

    # ── Тема ─────────────────────────────────────────────────────────────────

    def _refresh_styles(self):
        c = get_colors(self._theme)

        self._title_lbl.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{c['text']};")
        self._sep.setStyleSheet(f"color:{c['border']};")

        # Hero — всегда тёмный градиент (не меняем)

        # Update card
        self._update_card.setStyleSheet(f"""
            QWidget {{
                background: {c['bg_panel']};
                border: 1px solid {c['border']};
                border-radius: 12px;
            }}
        """)
        self._upd_title.setStyleSheet(
            f"font-size:12px; font-weight:600; color:{c['text_muted']};"
            "background:transparent; text-transform:uppercase; letter-spacing:0.5px;")
        if self._update_lbl:
            self._update_lbl.setStyleSheet(
                f"font-size:14px; font-weight:600; color:{c['text']}; background:transparent;")

        # Team card
        self._team_card.setStyleSheet(f"""
            QWidget {{
                background: {c['bg_panel']};
                border: 1px solid {c['border']};
                border-radius: 12px;
            }}
        """)

        for card in self._link_cards:
            card.apply_theme(self._theme)
