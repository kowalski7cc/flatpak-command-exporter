FROM debian:trixie

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        debhelper \
        debhelper-compat \
        dh-sequence-python3 \
        dpkg-dev \
        flatpak \
        gir1.2-adw-1 \
        gir1.2-flatpak-1.0 \
        gir1.2-gtk-4.0 \
        git \
        pybuild-plugin-pyproject \
        python3 \
        python3-dev \
        python3-gi \
        python3-pip \
        python3-setuptools \
        python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" \
        --create-home --shell /bin/bash "${USERNAME}"

USER ${USERNAME}
WORKDIR /workspaces/flatpak-command-exporter
