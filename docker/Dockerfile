# 1994 Mac render-farm node — patched Basilisk II (ADB control server) + headless X.
# Each container = one emulated Macintosh with its own AppleTalk name, networked to the
# other nodes over a shared virtual Ethernet (Basilisk udptunnel) for EtherTalk/NetRenderMan.
#
# Multi-stage: the emulator is COMPILED inside the image so it matches the runtime glibc.

# ---- build stage ----
FROM debian:bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential autoconf automake libsdl2-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
COPY macemu-src /src
WORKDIR /src/BasiliskII/src/Unix
RUN NO_CONFIGURE=1 ./autogen.sh \
    && ./configure --enable-sdl-video --enable-sdl-audio --disable-vosf --without-gtk --without-mon \
    && make -j"$(nproc)" \
    && strip BasiliskII

# ---- runtime stage ----
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      libsdl2-2.0-0 xvfb x11-utils x11-apps xauth \
      netcat-openbsd imagemagick procps iputils-ping \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/BasiliskII/src/Unix/BasiliskII /opt/mac/BasiliskII
COPY assets/mac.rom     /opt/mac/mac.rom
COPY assets/stuffit.img /opt/mac/stuffit.img
COPY entrypoint.sh      /opt/mac/entrypoint.sh
RUN chmod +x /opt/mac/BasiliskII /opt/mac/entrypoint.sh

VOLUME ["/os", "/shared"]
EXPOSE 6560
ENTRYPOINT ["/opt/mac/entrypoint.sh"]
