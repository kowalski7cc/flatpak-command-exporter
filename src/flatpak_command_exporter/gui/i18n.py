from gettext import NullTranslations, translation
from pathlib import Path
from typing import Callable, Final


_DOMAIN: Final[str] = "flatpak-command-exporter"
_LOCALE_DIR: Final[Path] = Path(__file__).with_name("locale")
_translator: NullTranslations = translation(
    _DOMAIN, localedir=str(_LOCALE_DIR), fallback=True
)
_: Callable[[str], str] = _translator.gettext
