#!/usr/bin/env bash
# build.sh — локальная сборка для macOS и Linux
# Использование: ./build.sh [--no-dmg] [--no-appimage]
set -euo pipefail

# ── Цвета ─────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC}  $*"; exit 1; }
step()    { echo -e "\n${BOLD}── $* ──${NC}"; }

# ── Аргументы ─────────────────────────────────────────────────────────────
BUILD_DMG=true
BUILD_APPIMAGE=true
for arg in "$@"; do
    case $arg in
        --no-dmg)       BUILD_DMG=false ;;
        --no-appimage)  BUILD_APPIMAGE=false ;;
    esac
done

# ── Версия ────────────────────────────────────────────────────────────────
VERSION=$(python3 -c "from version import __version__; print(__version__)" 2>/dev/null || echo "dev")
PLATFORM=$(uname -s)
ARCH=$(uname -m)
info "Версия: $VERSION  |  Платформа: $PLATFORM $ARCH"

# ── Проверки ──────────────────────────────────────────────────────────────
step "1 / Проверка зависимостей"
command -v python3  >/dev/null || error "python3 не найден"
command -v pyinstaller >/dev/null || {
    warn "pyinstaller не найден, устанавливаю..."
    pip3 install pyinstaller
}
success "Зависимости OK"

# ── PyInstaller ───────────────────────────────────────────────────────────
step "2 / PyInstaller"
pyinstaller LessonRecorder.spec --clean --noconfirm
success "PyInstaller OK  →  dist/"

# ── macOS: создаём .dmg ───────────────────────────────────────────────────
if [[ "$PLATFORM" == "Darwin" && "$BUILD_DMG" == "true" ]]; then
    step "3 / macOS DMG"
    APP="dist/LessonRecorder.app"
    DMG_NAME="LessonRecorder_v${VERSION}_macOS_${ARCH}.dmg"
    DMG_PATH="dist/$DMG_NAME"

    if [[ ! -d "$APP" ]]; then
        error "$APP не найден. Проверь LessonRecorder.spec (console=False, onedir)."
    fi

    # Создаём .dmg через hdiutil (встроен в macOS, без доп. зависимостей)
    TMP_DMG="dist/tmp_rw.dmg"
    rm -f "$TMP_DMG" "$DMG_PATH"

    info "Создаю readwrite-образ..."
    hdiutil create \
        -size 500m \
        -fs HFS+ \
        -volname "LessonRecorder" \
        -srcfolder "$APP" \
        "$TMP_DMG"

    info "Конвертирую в compressed DMG..."
    hdiutil convert "$TMP_DMG" \
        -format UDZO \
        -imagekey zlib-level=9 \
        -o "$DMG_PATH"

    rm -f "$TMP_DMG"
    success "DMG готов: $DMG_PATH"

    # Опционально: codesign (нужен Developer ID)
    if [[ -n "${CODESIGN_ID:-}" ]]; then
        info "Подписываю приложение (CODESIGN_ID=$CODESIGN_ID)..."
        codesign --force --deep --sign "$CODESIGN_ID" "$APP"
        success "Codesign OK"
    else
        warn "CODESIGN_ID не задан — приложение не подписано (для распространения нужна подпись)."
    fi
fi

# ── Linux: создаём AppImage ───────────────────────────────────────────────
if [[ "$PLATFORM" == "Linux" && "$BUILD_APPIMAGE" == "true" ]]; then
    step "3 / Linux AppImage"
    DIST_DIR="dist/LessonRecorder"  # onedir output

    if [[ ! -d "$DIST_DIR" ]]; then
        error "$DIST_DIR не найден. Проверь LessonRecorder.spec."
    fi

    APPIMAGE_TOOL="dist/appimagetool"
    if [[ ! -x "$APPIMAGE_TOOL" ]]; then
        info "Скачиваю appimagetool..."
        APPIMAGE_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
        [[ "$ARCH" == "aarch64" ]] && \
            APPIMAGE_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-aarch64.AppImage"
        curl -L "$APPIMAGE_URL" -o "$APPIMAGE_TOOL"
        chmod +x "$APPIMAGE_TOOL"
    fi

    # Готовим AppDir
    APPDIR="dist/AppDir"
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

    # Копируем бинарники
    cp -r "$DIST_DIR/"* "$APPDIR/usr/bin/"

    # .desktop файл
    cat > "$APPDIR/LessonRecorder.desktop" <<EOF
[Desktop Entry]
Name=LessonRecorder
Exec=LessonRecorder
Icon=LessonRecorder
Type=Application
Categories=Education;AudioVideo;
EOF
    cp "$APPDIR/LessonRecorder.desktop" \
       "$APPDIR/usr/share/applications/LessonRecorder.desktop"

    # Иконка
    if [[ -f "app_icon.png" ]]; then
        cp app_icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/LessonRecorder.png"
        cp app_icon.png "$APPDIR/LessonRecorder.png"
    fi

    # AppRun
    cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/LessonRecorder" "$@"
EOF
    chmod +x "$APPDIR/AppRun"

    # Собираем AppImage
    APPIMAGE_OUT="dist/LessonRecorder_v${VERSION}_Linux_${ARCH}.AppImage"
    ARCH=$ARCH "$APPIMAGE_TOOL" "$APPDIR" "$APPIMAGE_OUT"
    chmod +x "$APPIMAGE_OUT"
    success "AppImage готов: $APPIMAGE_OUT"

    # Также создаём .tar.gz (альтернатива)
    TAR_NAME="LessonRecorder_v${VERSION}_Linux_${ARCH}.tar.gz"
    tar -czf "dist/$TAR_NAME" -C dist LessonRecorder
    success "tar.gz готов: dist/$TAR_NAME"
fi

# ── Итог ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Сборка завершена успешно!${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════${NC}"
ls -lh dist/*.dmg dist/*.AppImage dist/*.tar.gz 2>/dev/null || true
echo ""
