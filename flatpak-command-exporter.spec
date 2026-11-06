%global debug_package %{nil}

Name:           flatpak-command-exporter
Version:        %(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
Release:        1%{?dist}
Summary:        Export commands provided by installed Flatpak applications
License:        MIT
URL:            https://github.com/kowalski7cc/flatpak-command-exporter
Source0:        %{name}-%{version}-%{release}.tar.xz
BuildArch:      noarch

BuildRequires:  flatpak-devel
BuildRequires:  polkit
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel

Requires:       dbus
Requires:       flatpak
Requires:       polkit

%description
Flatpak Command Exporter discovers commands declared by installed Flatpak
applications and creates launchers for them. This package provides the Python
library, command-line interface, and system integration.

%package gui
Summary:        Graphical interface for Flatpak Command Exporter
Requires:       %{name} = %{version}-%{release}
Requires:       gtk4
# The GUI loads GTK and Adw through GObject introspection rather than ELF links.
Requires:       libadwaita

%description gui
Flatlink is the graphical interface for inspecting and configuring Flatpak
command exports.

%generate_buildrequires
%pyproject_buildrequires

%prep
%autosetup -n %{name}-%{version} -p1

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files flatpak_command_exporter

install -Dpm 0644 src/flatpak_command_exporter/flatpak-exported-commands.sh \
    %{buildroot}%{_sysconfdir}/profile.d/flatpak-exported-commands.sh
install -Dpm 0644 resources/xyz.kowalski7cc.FlatpakCommandExporter.service \
    %{buildroot}%{_datadir}/dbus-1/system-services/xyz.kowalski7cc.FlatpakCommandExporter.service
install -Dpm 0644 resources/xyz.kowalski7cc.flatpak-command-exporter.policy \
    %{buildroot}%{_datadir}/polkit-1/actions/xyz.kowalski7cc.flatpak-command-exporter.policy

%check
PYTHONPATH=src %{python3} -m unittest discover -s tests -v

%files -f %{pyproject_files}
%doc README.md
%license LICENSE
%{_bindir}/flatshell
%exclude %{python3_sitelib}/flatpak_command_exporter/gui.py
%exclude %{python3_sitelib}/flatpak_command_exporter/__pycache__/gui*.pyc
%exclude %{_bindir}/flatlink
%exclude %{_datadir}/applications/xyz.kowalski7cc.flatpak-command-exporter.desktop
%exclude %{_datadir}/metainfo/xyz.kowalski7cc.flatpak-command-exporter.metainfo.xml
%exclude %{_datadir}/icons/hicolor/scalable/apps/xyz.kowalski7cc.flatpak-command-exporter.svg
%exclude %{_datadir}/icons/hicolor/symbolic/apps/xyz.kowalski7cc.flatpak-command-exporter-symbolic.svg
%config(noreplace) %{_sysconfdir}/profile.d/flatpak-exported-commands.sh
%{_datadir}/dbus-1/system-services/xyz.kowalski7cc.FlatpakCommandExporter.service
%{_datadir}/polkit-1/actions/xyz.kowalski7cc.flatpak-command-exporter.policy

%files gui
%{python3_sitelib}/flatpak_command_exporter/gui.py
%{python3_sitelib}/flatpak_command_exporter/__pycache__/gui*.pyc
%{_bindir}/flatlink
%{_datadir}/applications/xyz.kowalski7cc.flatpak-command-exporter.desktop
%{_datadir}/metainfo/xyz.kowalski7cc.flatpak-command-exporter.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/xyz.kowalski7cc.flatpak-command-exporter.svg
%{_datadir}/icons/hicolor/symbolic/apps/xyz.kowalski7cc.flatpak-command-exporter-symbolic.svg

%changelog
* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.8.0-1
- Release 0.8.0.

* Thu Nov 05 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.6.0-1
- Add Fedora RPM packages
