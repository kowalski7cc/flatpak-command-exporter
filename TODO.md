- Add a toggle to evry app_id, not only to the single exported command. This toplevel toggle should disable every command of the app
- Add a button with a system symbolic icon to represent that new commands should not be automatically exported to the system.
- Replace the toggle in the header to be a button with a system symbolic icon to represent that global commands should not be automatically exported.
- Edit the search bar to be the same height as the dropdown for filter selection.
- Add a button to the header to export all commands, similar to flatshell export, in case a new app was installed, use a system symbolic icon.
- Add an about page, it should be accessible in a menu voice from the hamburger menu in the header bar. Use Adwaita components anf GNOME Hig design. Informations abouth authors and version should arrive from pyproject.toml
- Update the exported library if a userful function is added
- Deduplicate added code between gui and cli if possible

Rules:

- Check AGENTS, DEVELOPERS and README before starting implementation
- Update documentation on finish.