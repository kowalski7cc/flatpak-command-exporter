FROM fedora:45

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

RUN dnf install -y \
        cairo-gobject-devel \
        flatpak \
        flatpak-devel \
        gcc \
        git \
        gobject-introspection-devel \
        gtk4 \
        gtk4-devel \
        libadwaita \
        libadwaita-devel \
        make \
        pkgconf-pkg-config \
        python3 \
        python3-devel \
        python3-pip \
        python3-gobject \
        redhat-rpm-config \
        rpm-build \
        rpmdevtools \
        rpmlint \
        shadow-utils \
    && dnf clean all

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" \
        --create-home --shell /bin/bash "${USERNAME}"

USER ${USERNAME}
WORKDIR /workspaces/flatpak-command-exporter
