# shellcheck shell=sh
USER_BASE="${XDG_DATA_HOME:-"$HOME/.local/share"}/flatpak-commands"
SYSTEM_ROOT="$(flatpak --installations 2>/dev/null | sed -n '1p')"
SYSTEM_BASE=
if [ -n "$SYSTEM_ROOT" ]; then
    SYSTEM_BASE="${SYSTEM_ROOT%/}-commands"
fi

if [ -d "$USER_BASE" ]; then
    case "$PATH" in
        "$USER_BASE"|"$USER_BASE":*) ;;
        *) PATH="$USER_BASE${PATH:+:$PATH}" ;;
    esac
fi

if [ -n "$SYSTEM_BASE" ] && [ -d "$SYSTEM_BASE" ]; then
    case "$PATH" in
        "$USER_BASE")
            PATH="$USER_BASE:$SYSTEM_BASE"
            ;;
        "$USER_BASE":*)
            PATH_REST="${PATH#"$USER_BASE":}"
            case ":$PATH_REST:" in
                *":$SYSTEM_BASE:"*) ;;
                *) PATH="$USER_BASE:$SYSTEM_BASE:$PATH_REST" ;;
            esac
            ;;
        "$SYSTEM_BASE"|"$SYSTEM_BASE":*) ;;
        *) PATH="$SYSTEM_BASE${PATH:+:$PATH}" ;;
    esac
fi

export PATH
