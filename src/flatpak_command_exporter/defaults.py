import textwrap
DEFAULT_EXPORT_COMMANDS = {
    "org.gimp.GIMP": {
        "gimp": "gimp"
    },
    "de.wwwtech.gitte": {
        "gitte": "gitte"
    },
    "org.audacityteam.Audacity": {
        "audacity": "audacity"
    },
    "org.milkytracker.MilkyTracker": {
        "milkytracker": "milkytracker"
    },
    "org.videolan.VLC": {
        "vlc": "vlc"
    },
    "org.getzola.zola": {
        "zola": "zola"
    },
    "org.gnome.Builder": {
        "builder": "builder"
    },
    "org.flatpak.Builder": {
        "flatpak-builder": "flatpak-builder"
    },
    "com.vscodium.codium": {
        "codium": "codium"
    },
    "com.vscodium.codium-insiders": {
        "codium-insiders": "codium-insiders"
    },
    "com.visualstudio.code": {
        "code": "code"
    },
    "com.github.k4zmu2a.spacecadetpinball": {
        "pinball": "SpaceCadetPinball"
    },
    "org.gnome.gitg": {
        "gitg": "gitg"
    },
    "org.mozilla.firefox": {
        "firefox": "firefox"
    },
    "com.google.Chrome": {
        "google-chrome": "chrome"
    },
    "com.google.ChromeDev": {
        "google-chrome-dev": "chrome"
    },
    "org.chromium.Chromium": {
        "chromium": "chromium"
    },
    "io.github.ungoogled_software.ungoogled_chromium": {
        "ungoogled-chromium": "ungoogled-chromium"
    },
    "com.usebottles.bottles": {
        "bottles": "bottles"
    },
    "com.obsproject.Studio": {
        "obs": "obs"
    },
    "org.libreoffice.LibreOffice": {
        "libreoffice": "libreoffice"
    },
    "org.gnome.baobab": {
        "baobab": "baobab"
    },
    "org.gnome.Showtime": {
        "showtime": "showtime"
    },
    "org.gnome.Decibels": {
        "decibels": "org.gnome.Decibels"
    },
    "org.virt_manager.virt-viewer": {
        "remote-viewer": "remote-viewer"
    },
    "org.gnome.Papers": {
        "papers": "papers"
    },
    "org.gnome.Loupe": {
        "loupe": "loupe"
    },
    "org.gnome.font-viewer": {
        "gnome-font-viewer": "gnome-font-viewer"
    },
    "org.remmina.Remmina": {
        "remmina": "remmina"
    },
    "org.gnome.seahorse.Application": {
        "seahorse": "seahorse"
    },
    "org.gnome.clocks": {
        "gnome-clocks": "gnome-clocks"
    },
    "org.localsend.localsend_app": {
        "localsend": "localsend"
    },
    "io.kinvolk.Headlamp": {
        "headlamp": "run-headlamp.sh"
    },
    "org.gnome.FileRoller": {
        "file-roller": "file-roller"
    },
    "org.gnome.Evolution": {
        "evolution": "evolution"
    },
    "org.gnome.TextEditor": {
        "gnome-text-editor": "gnome-text-editor"
    },
    "org.gnome.gedit": {
        "gedit": "gedit"
    },
    "org.gnome.NautilusPreviewer": {
        "sushi": "sushi"
    },
    "com.github.tchx84.Flatseal": {
        "flatseal": "com.github.tchx84.Flatseal"
    },
    "com.valvesoftware.Steam": {
        "steam": "steam"
    },
    "org.cockpit_project.CockpitClient": {
        "cockpit-client": "cockpit-client"
    },
    "org.filezillaproject.Filezilla": {
        "filezilla": "filezilla"
    },
    "org.virt_manager.virt-manager": {
        "virt-manager": "virt-manager"
    },
    "org.virt_manager.virt-viewer": {
        "remote-viewer": "remote-viewer"
    },
    "net.awalter.SuperHaxagon": {
        "SuperHaxagon": "/app/SuperHaxagon"
    },
    "uk.org.greenend.chiark.sgtatham.putty": {
        "putty": "putty",
        "puttygen": "puttygen",
        "psftp": "psftp",
        "pageant": "pageant",
        "pscp": "pscp"
    }
}

COMMAND_TEMPLATE = textwrap.dedent("""\
    #!/bin/sh
    for arg do
        shift
        if [ -e "$arg" ]; then
            set -- "$@" "@@" "$(readlink -f "$arg")" "@@"
        else
            set -- "$@" "$arg"
        fi
    done
    exec /usr/bin/flatpak run --branch={BRANCH} --arch={ARCH} --command={COMMAND} --file-forwarding {APP_ID} "$@"
    """)