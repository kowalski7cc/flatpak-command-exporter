def set_accessible_label(widget, Gtk, label: str) -> None:
	widget.update_property(
		[Gtk.AccessibleProperty.LABEL], [label]
	)


def set_decorative(widget, Gtk) -> None:
	widget.set_accessible_role(Gtk.AccessibleRole.PRESENTATION)
