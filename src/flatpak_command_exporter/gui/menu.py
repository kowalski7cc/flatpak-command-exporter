def create_main_menu(Gio):
	menu_model = Gio.Menu()
	menu_model.append("Settings", "app.settings")
	menu_model.append("About", "app.about")
	return menu_model
