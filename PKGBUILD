# Maintainer: Kowalski Dragon <kowalski7cc@users.noreply.github.com>
pkgname=('flatpak-command-exporter' 'flatpak-command-exporter-gui')
pkgver=$(python3 -c 'import pathlib, tomllib; print(tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"])')
pkgrel=1
pkgdesc='Export commands provided by installed Flatpak applications'
arch=('any')
url='https://github.com/kowalski7cc/flatpak-command-exporter'
license=('MIT')
depends=('flatpak' 'python>=3.13' 'python-gobject')
makedepends=('gtk4' 'hicolor-icon-theme' 'libadwaita' 'python-shtab')
source=(".flatpak-command-exporter-$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    cd "$srcdir/flatpak-command-exporter-$pkgver"
    make completion
}

package_flatpak-command-exporter() {
    cd "$srcdir/flatpak-command-exporter-$pkgver"

    local site_packages
    site_packages=$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
    install -d "$pkgdir$site_packages"
    cp -a src/flatpak_command_exporter "$pkgdir$site_packages/"
    rm -rf "$pkgdir$site_packages/flatpak_command_exporter/gui"
    find "$pkgdir$site_packages/flatpak_command_exporter" \
        -type d -name __pycache__ -prune -exec rm -rf {} +
    find "$pkgdir$site_packages/flatpak_command_exporter" \
        -type f -name '*.py[co]' -delete

    install -Dm755 /dev/stdin "$pkgdir/usr/bin/flatshell" <<'EOF'
#!/usr/bin/python
from flatpak_command_exporter.__main__ import main
main()
EOF
    install -Dm644 build/bash-completion/flatshell \
        "$pkgdir/usr/share/bash-completion/completions/flatshell"
    install -Dm644 src/flatpak_command_exporter/flatpak-exported-commands.sh \
        "$pkgdir/etc/profile.d/flatpak-exported-commands.sh"
    install -Dm644 resources/flatpak-command-exporter-system.timer \
        "$pkgdir/usr/lib/systemd/system/flatpak-command-exporter-system.timer"
    install -Dm644 resources/flatpak-command-exporter-system.service \
        "$pkgdir/usr/lib/systemd/system/flatpak-command-exporter-system.service"
    install -Dm644 resources/flatpak-command-exporter-user.timer \
        "$pkgdir/usr/lib/systemd/user/flatpak-command-exporter-user.timer"
    install -Dm644 resources/flatpak-command-exporter-user.service \
        "$pkgdir/usr/lib/systemd/user/flatpak-command-exporter-user.service"
    install -Dm644 resources/flatpak-command-exporter-system.preset \
        "$pkgdir/usr/lib/systemd/system-preset/80-flatpak-command-exporter.preset"
    install -Dm644 resources/flatpak-command-exporter-user.preset \
        "$pkgdir/usr/lib/systemd/user-preset/80-flatpak-command-exporter.preset"
    install -Dm644 LICENSE \
        "$pkgdir/usr/share/licenses/flatpak-command-exporter/LICENSE"
}

package_flatpak-command-exporter-gui() {
    pkgdesc='Graphical interface for Flatpak Command Exporter'
    depends=(
        'flatpak-command-exporter'
        'gtk4'
        'hicolor-icon-theme'
        'libadwaita'
        'python>=3.13'
        'python-gobject'
    )
    cd "$srcdir/flatpak-command-exporter-$pkgver"

    local site_packages
    site_packages=$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
    install -d "$pkgdir$site_packages/flatpak_command_exporter"
    cp -a src/flatpak_command_exporter/gui \
        "$pkgdir$site_packages/flatpak_command_exporter/"
    find "$pkgdir$site_packages/flatpak_command_exporter" \
        -type d -name __pycache__ -prune -exec rm -rf {} +
    find "$pkgdir$site_packages/flatpak_command_exporter" \
        -type f -name '*.py[co]' -delete
    install -Dm755 /dev/stdin "$pkgdir/usr/bin/flatlink" <<'EOF'
#!/usr/bin/python
from flatpak_command_exporter.gui import main
main()
EOF
    install -Dm644 resources/xyz.kowalski7cc.flatpak-command-exporter.desktop \
        "$pkgdir/usr/share/applications/xyz.kowalski7cc.flatpak-command-exporter.desktop"
    install -Dm644 resources/xyz.kowalski7cc.flatpak-command-exporter.metainfo.xml \
        "$pkgdir/usr/share/metainfo/xyz.kowalski7cc.flatpak-command-exporter.metainfo.xml"
    install -Dm644 resources/xyz.kowalski7cc.flatpak-command-exporter.svg \
        "$pkgdir/usr/share/icons/hicolor/scalable/apps/xyz.kowalski7cc.flatpak-command-exporter.svg"
    install -Dm644 resources/xyz.kowalski7cc.flatpak-command-exporter-symbolic.svg \
        "$pkgdir/usr/share/icons/hicolor/symbolic/apps/xyz.kowalski7cc.flatpak-command-exporter-symbolic.svg"
    install -Dm644 LICENSE \
        "$pkgdir/usr/share/licenses/flatpak-command-exporter-gui/LICENSE"
}
