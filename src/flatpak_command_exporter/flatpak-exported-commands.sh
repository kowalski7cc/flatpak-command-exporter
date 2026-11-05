# shellcheck shell=sh
USER_BASE="${XDG_DATA_HOME:-"$HOME/.local/share"}/flatpak-commands"
SYSTEM_BASE="/usr/share/flatpak-commands"

if [ -d "$USER_BASE" ]; then
    case ":$PATH:" in
        *":$USER_BASE:"*) ;;
        *) PATH="$USER_BASE:$PATH" ;;
    esac
fi

if [ -d "$SYSTEM_BASE" ]; then
    case ":$PATH:" in
        *":$SYSTEM_BASE:"*) ;;
        *) PATH="$SYSTEM_BASE:$PATH" ;;
    esac
fi

export PATH
