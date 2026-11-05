.PHONY: changelog deb tests clean

changelog:
	@version=$$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'); \
	debian_version="$$version-1"; \
	test "$$(dpkg-parsechangelog -SVersion)" = "$$debian_version" || \
		dch --newversion "$$debian_version" --distribution unstable "Release $$version."

deb:
	DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -us -uc -b

tests:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

clean:
	dpkg-buildpackage -T clean
