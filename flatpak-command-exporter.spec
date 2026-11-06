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
BuildRequires:  pyproject-rpm-macros
BuildRequires:  systemd-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-shtab
BuildRequires:  gettext

Requires:       flatpak
%systemd_requires

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
make translations
%pyproject_wheel
make completion

%install
%pyproject_install
install -Dpm 0644 build/bash-completion/flatshell \
    %{buildroot}%{_datadir}/bash-completion/completions/flatshell
%pyproject_save_files flatpak_command_exporter

install -Dpm 0644 src/flatpak_command_exporter/flatpak-exported-commands.sh \
    %{buildroot}%{_sysconfdir}/profile.d/flatpak-exported-commands.sh
install -Dpm 0644 resources/flatpak-command-exporter-system.timer \
    %{buildroot}%{_unitdir}/flatpak-command-exporter-system.timer
install -Dpm 0644 resources/flatpak-command-exporter-system.service \
    %{buildroot}%{_unitdir}/flatpak-command-exporter-system.service
install -Dpm 0644 resources/flatpak-command-exporter-user.timer \
    %{buildroot}%{_userunitdir}/flatpak-command-exporter-user.timer
install -Dpm 0644 resources/flatpak-command-exporter-user.service \
    %{buildroot}%{_userunitdir}/flatpak-command-exporter-user.service
install -Dpm 0644 resources/flatpak-command-exporter-system.preset \
    %{buildroot}%{_prefix}/lib/systemd/system-preset/80-flatpak-command-exporter.preset
install -Dpm 0644 resources/flatpak-command-exporter-user.preset \
    %{buildroot}%{_prefix}/lib/systemd/user-preset/80-flatpak-command-exporter.preset

%check
PYTHONPATH=src %{python3} -m unittest discover -s tests -v

%post
%systemd_post flatpak-command-exporter-system.timer
%systemd_user_post flatpak-command-exporter-user.timer

%preun
%systemd_preun flatpak-command-exporter-system.timer
%systemd_user_preun flatpak-command-exporter-user.timer

%postun
%systemd_postun flatpak-command-exporter-system.timer
%systemd_user_postun flatpak-command-exporter-user.timer

%files -f %{pyproject_files}
%doc README.md
%license LICENSE
%{_bindir}/flatshell
%{_datadir}/bash-completion/completions/flatshell
%exclude %{python3_sitelib}/flatpak_command_exporter/gui/*.py
%exclude %{python3_sitelib}/flatpak_command_exporter/gui/__pycache__/*.pyc
%exclude %{_bindir}/flatlink
%exclude %{_datadir}/applications/xyz.kowalski7cc.flatpak-command-exporter.desktop
%exclude %{_datadir}/metainfo/xyz.kowalski7cc.flatpak-command-exporter.metainfo.xml
%exclude %{_datadir}/icons/hicolor/scalable/apps/xyz.kowalski7cc.flatpak-command-exporter.svg
%exclude %{_datadir}/icons/hicolor/symbolic/apps/xyz.kowalski7cc.flatpak-command-exporter-symbolic.svg
%config(noreplace) %{_sysconfdir}/profile.d/flatpak-exported-commands.sh
%{_unitdir}/flatpak-command-exporter-system.timer
%{_unitdir}/flatpak-command-exporter-system.service
%{_prefix}/lib/systemd/system-preset/80-flatpak-command-exporter.preset
%{_userunitdir}/flatpak-command-exporter-user.timer
%{_userunitdir}/flatpak-command-exporter-user.service
%{_prefix}/lib/systemd/user-preset/80-flatpak-command-exporter.preset

%files gui
%{python3_sitelib}/flatpak_command_exporter/gui/
%{_bindir}/flatlink
%{_datadir}/applications/xyz.kowalski7cc.flatpak-command-exporter.desktop
%{_datadir}/metainfo/xyz.kowalski7cc.flatpak-command-exporter.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/xyz.kowalski7cc.flatpak-command-exporter.svg
%{_datadir}/icons/hicolor/symbolic/apps/xyz.kowalski7cc.flatpak-command-exporter-symbolic.svg

%changelog
* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.14.2-1
- Release 0.14.2.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.14.1-1
- Release 0.14.1.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.14.0-1
- Release 0.14.0.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.13.0-1
- Release 0.13.0.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.12.0-1
- Release 0.12.0.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.11.1-1
- Release 0.11.1.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.11.0-1
- Release 0.11.0.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.10.1-1
- Release 0.10.1.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.10.0-1
- Release 0.10.0.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.9.1-1
- Release 0.9.1.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.9.0-1
- Release 0.9.0.

* Fri Nov 06 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.8.0-1
- Release 0.8.0.

* Thu Nov 05 2026 Kowalski Dragon <kowalski7cc@users.noreply.github.com> - 0.6.0-1
- Add Fedora RPM packages
