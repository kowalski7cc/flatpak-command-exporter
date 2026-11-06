from .i18n import _


def create_main_menu(Gio) -> object:
	menu_model = Gio.Menu()
	menu_model.append(_("Settings"), "app.settings")
	menu_model.append(_("About"), "app.about")
	return menu_model
