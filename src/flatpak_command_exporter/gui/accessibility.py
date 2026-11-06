def set_accessible_label(widget, Gtk, label):
	widget.update_property(
		[Gtk.AccessibleProperty.LABEL], [label]
	)


def set_decorative(widget, Gtk):
	widget.set_accessible_role(Gtk.AccessibleRole.PRESENTATION)
