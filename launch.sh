#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Wortfall requires Python 3."
    read -r -p "Press Enter to close..."
    exit 1
fi

# If started from an existing terminal, use that terminal instead of opening another.
if [[ -t 1 ]]; then
    exec python3 "$APP_DIR/main.py"
fi

# Double-click launch: open a terminal emulator available on Arch Linux.
if command -v kitty >/dev/null 2>&1; then
    exec kitty -- bash -lc 'cd "$1"; python3 main.py; status=$?; echo; read -rp "Wortfall closed (exit $status). Press Enter to close..."; exit "$status"' _ "$APP_DIR"
elif command -v xfce4-terminal >/dev/null 2>&1; then
    exec xfce4-terminal --hold --command "bash -lc 'cd \"$APP_DIR\"; python3 main.py; status=\$?; echo; read -rp \"Wortfall closed (exit \$status). Press Enter to close...\"; exit \$status'"
elif command -v konsole >/dev/null 2>&1; then
    exec konsole --hold -e bash -lc 'cd "$1"; python3 main.py; status=$?; echo; read -rp "Wortfall closed (exit $status). Press Enter to close..."; exit "$status"' _ "$APP_DIR"
elif command -v gnome-terminal >/dev/null 2>&1; then
    exec gnome-terminal -- bash -lc 'cd "$1"; python3 main.py; status=$?; echo; read -rp "Wortfall closed (exit $status). Press Enter to close..."; exit "$status"' _ "$APP_DIR"
elif command -v alacritty >/dev/null 2>&1; then
    exec alacritty -e bash -lc 'cd "$1"; python3 main.py; status=$?; echo; read -rp "Wortfall closed (exit $status). Press Enter to close..."; exit "$status"' _ "$APP_DIR"
elif command -v foot >/dev/null 2>&1; then
    exec foot bash -lc 'cd "$1"; python3 main.py; status=$?; echo; read -rp "Wortfall closed (exit $status). Press Enter to close..."; exit "$status"' _ "$APP_DIR"
elif command -v xterm >/dev/null 2>&1; then
    exec xterm -hold -e bash -lc 'cd "$1"; python3 main.py; status=$?; echo; read -rp "Wortfall closed (exit $status). Press Enter to close..."; exit "$status"' _ "$APP_DIR"
else
    cat <<'MSG'
No supported terminal emulator was found.
Install one (for example: sudo pacman -S xfce4-terminal)
or run ./launch.sh from an open terminal.
MSG
    read -r -p "Press Enter to close..."
    exit 1
fi
