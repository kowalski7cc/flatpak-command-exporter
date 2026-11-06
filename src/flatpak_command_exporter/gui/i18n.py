from gettext import translation
from pathlib import Path


_DOMAIN = "flatpak-command-exporter"
_LOCALE_DIR = Path(__file__).with_name("locale")
_translator = translation(_DOMAIN, localedir=str(_LOCALE_DIR), fallback=True)
_ = _translator.gettext
