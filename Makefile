.PHONY: deb clean

deb:
	dpkg-buildpackage -us -uc -b

clean:
	dpkg-buildpackage -T clean
