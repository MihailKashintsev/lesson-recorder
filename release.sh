#!/usr/bin/env bash
# release.sh — публикация релиза LessonRecorder
# Работает на macOS и Linux
# Использование: bash release.sh
# Или с параметрами: bash release.sh 1.2.0 "Исправлены баги"

set -euo pipefail

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  ✅  $*${NC}"; }
err()  { echo -e "${RED}  ❌  $*${NC}"; exit 1; }
step() { echo -e "\n${CYAN}${BOLD}>>> $*${NC}"; }

echo ""
echo -e "${BOLD}  🚀 LessonRecorder Release Tool${NC}"
echo ""

# ── Python ────────────────────────────────────────────────────────────────────
PYTHON=""
for CMD in python3 python; do
    if command -v "$CMD" >/dev/null 2>&1; then
        PYTHON="$CMD"; break
    fi
done
[[ -z "$PYTHON" ]] && err "python3 не найден"

# Если есть venv — используем его
[[ -f ".venv/bin/python3" ]] && PYTHON=".venv/bin/python3"

# ── Версия ────────────────────────────────────────────────────────────────────
step "Текущая версия"
CURRENT=$("$PYTHON" -c "from version import __version__; print(__version__)")
echo -e "  Сейчас: ${BOLD}v${CURRENT}${NC}"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo ""
    read -rp "  Новая версия (например 1.2.0): " VERSION
fi

if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    err "Неверный формат. Используй X.Y.Z, например 1.2.0"
fi
TAG="v$VERSION"

# ── Changelog ─────────────────────────────────────────────────────────────────
CHANGELOG="${2:-}"
if [[ -z "$CHANGELOG" ]]; then
    echo ""
    echo -e "${YELLOW}  Что изменилось в $TAG?${NC}"
    echo "  Вводи по одному пункту, Enter на пустой строке — конец."
    echo ""
    LINES=()
    while true; do
        read -rp "  + " LINE
        [[ -z "$LINE" ]] && break
        LINES+=("$LINE")
    done
    CHANGELOG=$(printf '%s\n' "${LINES[@]}")
fi

[[ -z "$(echo "$CHANGELOG" | tr -d '[:space:]')" ]] && err "Changelog не может быть пустым"

echo ""
echo -e "  Версия:  ${BOLD}$TAG${NC}"
echo "  Изменения:"
while IFS= read -r line; do
    [[ -n "$line" ]] && echo "    - $line"
done <<< "$CHANGELOG"

# ── Незакоммиченные изменения ────────────────────────────────────────────────
step "Git статус"
GIT_STATUS=$(git status --porcelain)
if [[ -n "$GIT_STATUS" ]]; then
    echo -e "${YELLOW}  Есть незакоммиченные изменения:${NC}"
    echo "$GIT_STATUS" | sed 's/^/    /'
    echo ""
    read -rp "  Закоммитить всё? (y/n): " ANSWER
    if [[ "$ANSWER" == "y" ]]; then
        git add -A
        git commit -m "Release $TAG"
        ok "Закоммичено"
    else
        err "Закоммить вручную и запусти снова"
    fi
fi

# ── Бамп версии ───────────────────────────────────────────────────────────────
step "Обновляю версию"
"$PYTHON" bump_version.py "$VERSION"
ok "Версия обновлена до $VERSION"

git add version.py
for F in "installer/version_info.txt" "version_info.txt"; do
    [[ -f "$F" ]] && git add "$F"
done
git commit -m "Bump version to $VERSION"
ok "Закоммичено"

# ── Release notes ─────────────────────────────────────────────────────────────
step "Сохраняю release notes"
{
    echo "## What's new in $TAG"
    echo ""
    while IFS= read -r line; do
        [[ -n "$line" ]] && echo "- $line"
    done <<< "$CHANGELOG"
} > RELEASE_NOTES.md
ok "RELEASE_NOTES.md сохранён"

git add RELEASE_NOTES.md
git commit -m "Release notes for $TAG"
ok "Закоммичено"

# ── Тег ───────────────────────────────────────────────────────────────────────
step "Создаю тег $TAG"
if git tag -l "$TAG" | grep -q .; then
    err "Тег $TAG уже существует"
fi

FIRST_LINE=$(echo "$CHANGELOG" | head -1)
git tag -a "$TAG" -m "$FIRST_LINE"
ok "Тег $TAG создан"

# ── Push ──────────────────────────────────────────────────────────────────────
step "Пушу на GitHub"
BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo -e "  Пушу ветку ${BOLD}$BRANCH${NC}..."
git push origin "$BRANCH"
ok "Ветка запушена"

echo -e "  Пушу тег ${BOLD}$TAG${NC}..."
git push origin "$TAG"
ok "Тег запушен"

# ── Итог ──────────────────────────────────────────────────────────────────────
REMOTE=$(git remote get-url origin)
REPO_URL="${REMOTE%.git}"

echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  ✅ Релиз $TAG запущен!${NC}"
echo ""
echo -e "  Следи за сборкой: ${CYAN}$REPO_URL/actions${NC}"
echo -e "  Установщик будет готов через ~7 минут"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
