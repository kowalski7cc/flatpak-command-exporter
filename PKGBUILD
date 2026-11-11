# Maintainer: Kowalski Dragon <kowalski7cc@users.noreply.github.com>
pkgname=(
    'flatpak-command-exporter'
    'flatpak-command-exporter-core'
    'flatpak-command-exporter-cli'
    'flatpak-command-exporter-gui'
    'flatpak-command-exporter-service'
)
pkgver=$(python3 -c 'import pathlib, tomllib; print(tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"])')
pkgrel=1
pkgdesc='Export commands provided by installed Flatpak applications'
arch=('any')
url='https://github.com/kowalski7cc/flatpak-command-exporter'
license=('MIT')
makedepends=('gettext' 'python-shtab')
source=(".flatpak-command-exporter-$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    cd "$srcdir/flatpak-command-exporter-$pkgver"
    make translations completion
}

package_flatpak-command-exporter() {
    pkgdesc='Flatpak command exporter (metapackage)'
    depends=(
        'flatpak-command-exporter-cli'
        'flatpak-command-exporter-gui'
        'flatpak-command-exporter-service'
    )
    cd "$srcdir/flatpak-command-exporter-$pkgver"
    install -Dm644 LICENSE \
        "$pkgdir/usr/share/licenses/flatpak-command-exporter/LICENSE"
}

package_flatpak-command-exporter-core() {
    pkgdesc='Shared Python API for Flatpak Command Exporter'
    depends=('flatpak' 'python>=3.13' 'python-gobject')
    cd "$srcdir/flatpak-command-exporter-$pkgver"

    local site_packages
    site_packages=$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
    local package_dir="$pkgdir$site_packages/flatpak_command_exporter"
    install -d "$package_dir"
    cp -a src/flatpak_command_exporter/api "$package_dir/"
    install -Dm644 src/flatpak_command_exporter/__init__.py "$package_dir/__init__.py"
    install -Dm644 src/flatpak_command_exporter/application.py "$package_dir/application.py"
    install -Dm644 src/flatpak_command_exporter/config.py "$package_dir/config.py"
    install -Dm644 src/flatpak_command_exporter/defaults.py "$package_dir/defaults.py"
    install -Dm644 src/flatpak_command_exporter/py.typed "$package_dir/py.typed"
    find "$package_dir" -type d -name __pycache__ -prune -exec rm -rf {} +
    find "$package_dir" -type f -name '*.py[co]' -delete
    install -Dm644 LICENSE \
        "$pkgdir/usr/share/licenses/flatpak-command-exporter-core/LICENSE"
}

package_flatpak-command-exporter-cli() {
    pkgdesc='Command-line tools for Flatpak Command Exporter'
    depends=('flatpak-command-exporter-core')
    cd "$srcdir/flatpak-command-exporter-$pkgver"

    local site_packages
    site_packages=$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
    local package_dir="$pkgdir$site_packages/flatpak_command_exporter"
    install -d "$package_dir"
    install -Dm644 src/flatpak_command_exporter/__main__.py "$package_dir/__main__.py"
    install -Dm644 src/flatpak_command_exporter/cli.py "$package_dir/cli.py"
    install -Dm644 src/flatpak_command_exporter/cli_parser.py "$package_dir/cli_parser.py"
    install -Dm644 src/flatpak_command_exporter/profile.py "$package_dir/profile.py"
    install -Dm644 src/flatpak_command_exporter/flatpak-exported-commands.sh \
        "$package_dir/flatpak-exported-commands.sh"

    install -Dm755 /dev/stdin "$pkgdir/usr/bin/flatshell" <<'EOF'
#!/usr/bin/python
from flatpak_command_exporter.__main__ import main
main()
EOF
    install -Dm644 build/bash-completion/flatshell \
        "$pkgdir/usr/share/bash-completion/completions/flatshell"
    install -Dm644 LICENSE \
        "$pkgdir/usr/share/licenses/flatpak-command-exporter-cli/LICENSE"
}

package_flatpak-command-exporter-service() {
    pkgdesc='Automatic Flatpak command export service'
    depends=('flatpak-command-exporter-core' 'systemd')
    install=service/flatpak-command-exporter.install
    cd "$srcdir/flatpak-command-exporter-$pkgver"

    local site_packages
    site_packages=$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
    local package_dir="$pkgdir$site_packages/flatpak_command_exporter"
    install -d "$package_dir"
    install -Dm644 src/flatpak_command_exporter/system_export.py \
        "$package_dir/system_export.py"
    cp -a src/flatpak_command_exporter/service "$package_dir/"
    find "$package_dir" -type d -name __pycache__ -prune -exec rm -rf {} +
    find "$package_dir" -type f -name '*.py[co]' -delete

    install -Dm644 src/flatpak_command_exporter/flatpak-exported-commands.sh \
        "$pkgdir/etc/profile.d/flatpak-exported-commands.sh"
    install -Dm644 service/flatpak-command-exporter-system.service \
        "$pkgdir/usr/lib/systemd/system/flatpak-command-exporter-system.service"
    install -Dm644 service/flatpak-command-exporter-user.service \
        "$pkgdir/usr/lib/systemd/user/flatpak-command-exporter-user.service"
    install -Dm644 service/flatpak-command-exporter-system.preset \
        "$pkgdir/usr/lib/systemd/system-preset/80-flatpak-command-exporter.preset"
    install -Dm644 service/flatpak-command-exporter-user.preset \
        "$pkgdir/usr/lib/systemd/user-preset/80-flatpak-command-exporter.preset"
    install -Dm644 LICENSE \
        "$pkgdir/usr/share/licenses/flatpak-command-exporter-service/LICENSE"
}

package_flatpak-command-exporter-gui() {
    pkgdesc='Graphical interface for Flatpak Command Exporter'
    depends=(
        'flatpak-command-exporter-core'
        'gtk4'
        'hicolor-icon-theme'
        'libadwaita'
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
