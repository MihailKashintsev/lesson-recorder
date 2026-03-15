#!/usr/bin/env bash
# install_python.sh — Автоустановка Python на macOS и Linux
# Запускается из установщика / при первом запуске приложения
# Использование: bash install_python.sh [--version 3.12]

set -euo pipefail

REQUIRED_VERSION="${PYTHON_VERSION:-3.12}"
MIN_VERSION="3.10"
PLATFORM="$(uname -s)"
ARCH="$(uname -m)"

# ── Цвета ─────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅  $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️   $*${NC}"; }
err()  { echo -e "${RED}❌  $*${NC}"; exit 1; }
info() { echo -e "ℹ️   $*"; }

# ── Аргументы ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version) REQUIRED_VERSION="$2"; shift 2 ;;
        *) shift ;;
    esac
done

echo "═══════════════════════════════════════════"
echo "  LessonRecorder — Python Setup"
echo "  Platform: $PLATFORM $ARCH"
echo "  Require:  Python $MIN_VERSION+"
echo "═══════════════════════════════════════════"

# ── Проверяем существующий Python ─────────────────────────────────────────
check_python() {
    local py
    for cmd in python3 python python3.12 python3.11 python3.10; do
        py=$(command -v "$cmd" 2>/dev/null || true)
        if [[ -n "$py" ]]; then
            local ver
            ver=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
            # Сравниваем версии
            if python3 -c "import sys; sys.exit(0 if tuple(map(int,'$ver'.split('.'))) >= tuple(map(int,'$MIN_VERSION'.split('.'))) else 1)" 2>/dev/null; then
                echo "$py"
                return 0
            fi
        fi
    done
    return 1
}

if EXISTING=$(check_python 2>/dev/null); then
    VER=$("$EXISTING" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    ok "Python $VER уже установлен: $EXISTING"
    exit 0
fi

info "Python $MIN_VERSION+ не найден — устанавливаю..."

# ════════════════════════════════════════════════════════
#  macOS
# ════════════════════════════════════════════════════════
if [[ "$PLATFORM" == "Darwin" ]]; then

    # Вариант 1: Homebrew
    if command -v brew >/dev/null 2>&1; then
        info "Homebrew найден — устанавливаю python@${REQUIRED_VERSION}..."
        brew install "python@${REQUIRED_VERSION}" || brew install python3
        ok "Python установлен через Homebrew"
        exit 0
    fi

    # Вариант 2: Официальный .pkg
    info "Homebrew не найден — скачиваю официальный Python .pkg..."

    if [[ "$ARCH" == "arm64" ]]; then
        PKG_URL="https://www.python.org/ftp/python/${REQUIRED_VERSION}.0/python-${REQUIRED_VERSION}.0-macos11.pkg"
    else
        PKG_URL="https://www.python.org/ftp/python/${REQUIRED_VERSION}.0/python-${REQUIRED_VERSION}.0-macos11.pkg"
    fi

    TMP_PKG="/tmp/python_installer.pkg"
    curl -L "$PKG_URL" -o "$TMP_PKG" --progress-bar

    info "Устанавливаю Python (потребуются права администратора)..."
    sudo installer -pkg "$TMP_PKG" -target /
    rm -f "$TMP_PKG"

    ok "Python установлен!"
    echo ""
    echo "  Перезапустите терминал или выполните:"
    echo "  export PATH=\"/Library/Frameworks/Python.framework/Versions/${REQUIRED_VERSION}/bin:\$PATH\""
    exit 0
fi

# ════════════════════════════════════════════════════════
#  Linux
# ════════════════════════════════════════════════════════
if [[ "$PLATFORM" == "Linux" ]]; then

    # Определяем дистрибутив
    DISTRO=""
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        DISTRO="${ID:-unknown}"
    fi

    info "Linux дистрибутив: ${DISTRO:-unknown}"

    install_via_apt() {
        info "apt: устанавливаю python${REQUIRED_VERSION}..."
        sudo apt-get update -qq
        # Сначала пробуем deadsnakes PPA для Ubuntu
        if command -v add-apt-repository >/dev/null 2>&1; then
            sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
            sudo apt-get update -qq
        fi
        sudo apt-get install -y \
            "python${REQUIRED_VERSION}" \
            "python${REQUIRED_VERSION}-venv" \
            "python${REQUIRED_VERSION}-dev" \
            "python3-pip" || \
        sudo apt-get install -y python3 python3-pip python3-venv
    }

    install_via_dnf() {
        info "dnf: устанавливаю python${REQUIRED_VERSION}..."
        sudo dnf install -y "python${REQUIRED_VERSION}" || \
        sudo dnf install -y python3
    }

    install_via_pacman() {
        info "pacman: устанавливаю python..."
        sudo pacman -S --noconfirm python python-pip
    }

    install_via_zypper() {
        info "zypper: устанавливаю python3..."
        sudo zypper install -y python3 python3-pip
    }

    # Выбираем менеджер пакетов
    if command -v apt-get >/dev/null 2>&1; then
        install_via_apt
    elif command -v dnf >/dev/null 2>&1; then
        install_via_dnf
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y python3 python3-pip
    elif command -v pacman >/dev/null 2>&1; then
        install_via_pacman
    elif command -v zypper >/dev/null 2>&1; then
        install_via_zypper
    else
        err "Не удалось определить менеджер пакетов.\nУстановите Python 3.10+ вручную."
    fi

    # Проверяем установку
    if INSTALLED=$(check_python 2>/dev/null); then
        VER=$("$INSTALLED" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
        ok "Python $VER установлен: $INSTALLED"
    else
        warn "Установка завершена, но Python не найден в PATH."
        warn "Перезапустите терминал и попробуйте снова."
    fi
    exit 0
fi

err "Неизвестная платформа: $PLATFORM"
