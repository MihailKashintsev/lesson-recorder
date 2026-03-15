#!/bin/bash
# ====================================================================
#  mac_setup.sh — Быстрый старт LessonRecorder на MacBook
#  Запуск: bash mac_setup.sh
#  НЕ нужно ничего устанавливать заранее — скрипт сделает всё сам.
# ====================================================================

set -euo pipefail

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✅  $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️   $*${NC}"; }
err()  { echo -e "${RED}❌  $*${NC}"; exit 1; }
info() { echo -e "${BLUE}ℹ️   $*${NC}"; }
step() { echo -e "\n${BOLD}━━━  $*  ━━━${NC}"; }

echo ""
echo -e "${BOLD}  🎙  LessonRecorder — Mac Setup${NC}"
echo -e "  macOS $(sw_vers -productVersion)  |  $(uname -m)"
echo ""

# ── Шаг 1: Python ────────────────────────────────────────────────────────────
step "1 / Проверка Python"

# Ищем python3 в нескольких местах
PYTHON=""
for CMD in python3.14 python3.13 python3.12 python3.11 python3 python; do
    FOUND=$(command -v "$CMD" 2>/dev/null || true)
    if [[ -n "$FOUND" ]]; then
        # Проверяем что версия >= 3.10
        VER=$("$FOUND" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [[ $MAJOR -ge 3 && $MINOR -ge 10 ]]; then
            PYTHON="$FOUND"
            break
        fi
    fi
done

# Также проверяем /Library/Frameworks (стандартный путь python.org installer)
if [[ -z "$PYTHON" ]]; then
    for VER_DIR in /Library/Frameworks/Python.framework/Versions/*/; do
        CANDIDATE="${VER_DIR}bin/python3"
        if [[ -x "$CANDIDATE" ]]; then
            VER=$("$CANDIDATE" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
            MAJOR=$(echo "$VER" | cut -d. -f1)
            MINOR=$(echo "$VER" | cut -d. -f2)
            if [[ $MAJOR -ge 3 && $MINOR -ge 10 ]]; then
                PYTHON="$CANDIDATE"
                break
            fi
        fi
    done
fi

if [[ -z "$PYTHON" ]]; then
    err "Python 3.10+ не найден. Установи: brew install python3"
fi

PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
ok "Python $PY_VER — $PYTHON"

# ── Шаг 2: Виртуальное окружение ─────────────────────────────────────────────
step "2 / Виртуальное окружение (.venv)"

if [[ ! -d ".venv" ]]; then
    info "Создаю .venv..."
    "$PYTHON" -m venv .venv
    ok ".venv создан"
else
    ok ".venv уже существует"
fi

# Активируем venv для текущего скрипта
source .venv/bin/activate
VENV_PY=".venv/bin/python3"
ok "venv активирован"

# ── Шаг 3: pip ───────────────────────────────────────────────────────────────
step "3 / Обновление pip"
"$VENV_PY" -m pip install --upgrade pip --quiet
ok "pip обновлён"

# ── Шаг 4: Portaudio (для sounddevice) ───────────────────────────────────────
step "4 / Системные зависимости macOS"

if command -v brew >/dev/null 2>&1; then
    info "Homebrew найден — устанавливаю portaudio..."
    brew install portaudio 2>/dev/null || warn "portaudio уже установлен или ошибка"
    ok "portaudio OK"
else
    warn "Homebrew не найден. Sounddevice может не работать без portaudio."
    warn "Установи Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
fi

# ── Шаг 5: Python пакеты ─────────────────────────────────────────────────────
step "5 / Установка Python зависимостей"

info "Устанавливаю базовые пакеты..."
"$VENV_PY" -m pip install \
    "PyQt6>=6.5.0" \
    "numpy>=1.24.0" \
    "scipy>=1.11.0" \
    "sounddevice>=0.4.6" \
    "requests>=2.31.0" \
    "packaging>=23.0" \
    "openai>=1.0.0" \
    --quiet
ok "Базовые пакеты"

info "Устанавливаю Whisper (займёт ~1-2 мин)..."
"$VENV_PY" -m pip install \
    "openai-whisper>=20231117" \
    "faster-whisper>=1.0.0" \
    --quiet
ok "Whisper"

info "Устанавливаю опциональные пакеты (OCR, Gemini)..."
"$VENV_PY" -m pip install \
    "pytesseract>=0.3.10" \
    "Pillow>=10.0.0" \
    "google-generativeai>=0.3.0" \
    --quiet 2>/dev/null || warn "Некоторые опциональные пакеты не установились (не критично)"
ok "Опциональные пакеты"

# opencv отдельно — он большой и иногда падает
"$VENV_PY" -m pip install "opencv-python>=4.8.0" --quiet 2>/dev/null && \
    ok "OpenCV (камера для OCR)" || \
    warn "OpenCV не установился — камера в OCR недоступна (не критично)"

# ── Шаг 6: Проверка ──────────────────────────────────────────────────────────
step "6 / Проверка установки"

CHECK_PACKAGES=("PyQt6" "numpy" "sounddevice" "openai" "requests")
ALL_OK=true
for PKG in "${CHECK_PACKAGES[@]}"; do
    if "$VENV_PY" -m pip show "$PKG" >/dev/null 2>&1; then
        ok "$PKG"
    else
        warn "$PKG — не найден!"
        ALL_OK=false
    fi
done

# ── Итог ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if $ALL_OK; then
    echo -e "${GREEN}${BOLD}  ✅ Установка завершена успешно!${NC}"
else
    echo -e "${YELLOW}${BOLD}  ⚠️  Установка завершена с предупреждениями${NC}"
fi
echo ""
echo -e "${BOLD}  Для запуска LessonRecorder:${NC}"
echo ""
echo -e "  ${BLUE}source .venv/bin/activate${NC}"
echo -e "  ${BLUE}python3 main.py${NC}"
echo ""
echo -e "${BOLD}  Или одной командой:${NC}"
echo -e "  ${BLUE}.venv/bin/python3 main.py${NC}"
echo ""
echo -e "${BOLD}  Для сборки .dmg:${NC}"
echo -e "  ${BLUE}chmod +x build.sh && ./build.sh${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
