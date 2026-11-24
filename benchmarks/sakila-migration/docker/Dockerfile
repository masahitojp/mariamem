FROM mariadb@sha256:4aaf88b3106382c8c18e49f0cec60267be618fc22f858c4503afb2a2555afed3
RUN --network=none --mount=type=bind,source=packages,target=/packages \
    DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::=--force-confold install /packages/*.deb \
    && rm -rf /var/lib/mysql/* \
    && test -z "$(ls -A /var/lib/mysql)" \
    && mariadbd --version
ENV MARIADB_VERSION=1:12.3.4+maria~ubu2404
