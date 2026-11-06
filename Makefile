BASE ?= flatpak-command-exporter

.PHONY: changelog metainfo spec release deb rpm apk completion translations tests clean

changelog:
	@version=$$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'); \
	debian_version="$$version-1"; \
	if [ "$$(dpkg-parsechangelog -SVersion)" != "$$debian_version" ]; then \
		if [ -n "$${SOURCE_DATE_EPOCH:-}" ]; then \
			release_date=$$(LC_ALL=C date -Ru -d "@$$SOURCE_DATE_EPOCH"); \
		else \
			release_date=$$(LC_ALL=C date -Ru); \
		fi; \
		dch --date "$$release_date" --newversion "$$debian_version" \
			--distribution unstable "Release $$version."; \
	fi

metainfo:
	python3 scripts/update_release_metadata.py metainfo

spec:
	python3 scripts/update_release_metadata.py spec

release: changelog spec metainfo

deb:
	DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -us -uc -b

rpm:
	rpmbuild -bb --build-in-place $(BASE).spec

apk:
	@set -eu; \
	version=$$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'); \
	source_archive=".flatpak-command-exporter-$$version.tar.gz"; \
	trap 'rm -f "$$source_archive" .PKGBUILD' EXIT; \
	sed "s/^pkgver=.*/pkgver=$$version/" PKGBUILD > .PKGBUILD; \
	git ls-files -z --cached --others --exclude-standard \
		| tar --null -T - --transform="s,^,$(BASE)-$$version/," -czf "$$source_archive"; \
	makepkg --force -p .PKGBUILD

completion:
	mkdir -p build/bash-completion
	PYTHONPATH=src shtab --shell=bash -u \
		flatpak_command_exporter.cli_parser.build_parser \
		> build/bash-completion/flatshell

translations:
	@set -eu; \
	mkdir -p build; \
	xgettext --language=Python --keyword=_ --from-code=UTF-8 \
		--output=build/flatpak-command-exporter.pot \
		src/flatpak_command_exporter/gui/application.py \
		src/flatpak_command_exporter/gui/settings.py \
		src/flatpak_command_exporter/gui/menu.py; \
	for catalog in po/*.po; do \
		language=$$(basename "$$catalog" .po); \
		output_dir="src/flatpak_command_exporter/gui/locale/$$language/LC_MESSAGES"; \
		mkdir -p "$$output_dir"; \
		msgcmp "$$catalog" build/flatpak-command-exporter.pot; \
		msgfmt --check --check-format \
			--output-file "$$output_dir/flatpak-command-exporter.mo" "$$catalog"; \
	done

tests:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

clean:
	dpkg-buildpackage -T clean
