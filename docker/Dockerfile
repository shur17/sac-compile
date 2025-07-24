FROM sequoiadb/sac-server-builder AS builder

WORKDIR /sac

COPY . .

RUN set -eux; \
    mkdir -p /sac/build/packages/; \
    cp ./docker/settings.xml /usr/share/maven/conf/settings.xml; \
    sed -i 's/fnm env/fnm env --shell=bash/' ~/.bashrc; \
    source ~/.bashrc; \
    ./build.sh

FROM sequoiadb/sac-server-runtime

ENV TZ=Asia/Shanghai

COPY --from=builder /sac/build/sac /opt/sequoiasac

COPY ./docker/docker-entrypoint.sh /docker-entrypoint.sh

RUN set -eux; \
    groupadd -r -g 1001 sdbadmin_group; \
    useradd -u 1001 -r -g 1001 -m -s /sbin/nologin -c "Default Sac User" sdbadmin; \
    chown 1001:1001 -R /opt/sequoiasac; \
    chown 1001:1001 /docker-entrypoint.sh; \
    mkdir -p /data/sac; \
    chown 1001:1001 -R /data/sac

VOLUME ["/data/sac"]

USER 1001

EXPOSE 28000

ENTRYPOINT ["/docker-entrypoint.sh"]