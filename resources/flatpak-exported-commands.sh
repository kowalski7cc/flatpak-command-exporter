# shellcheck shell=sh
BASE="${XDG_DATA_HOME:-"$HOME/.local/share"}/flatpak-commands"
if [ -d "$BASE" ]; then
    export PATH="$BASE:$PATH"
fi
