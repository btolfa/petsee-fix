# Official Traccar image with tracker-server.jar rebuilt from the same tag plus our Topin patch.
# See docs/adr/0001-mirror-into-native-topin.md.
ARG TRACCAR_VERSION=6.17.0

FROM eclipse-temurin:21-jdk AS build
ARG TRACCAR_VERSION
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -r /var/lib/apt/lists/*
RUN git clone --depth 1 --branch v${TRACCAR_VERSION} https://github.com/traccar/traccar.git /src
WORKDIR /src
COPY topin-lte-cells.patch /tmp/
RUN git apply /tmp/topin-lte-cells.patch
RUN ./gradlew --no-daemon test --tests org.traccar.protocol.TopinProtocolDecoderTest jar

FROM traccar/traccar:${TRACCAR_VERSION}-alpine
COPY --from=build /src/target/tracker-server.jar /opt/traccar/tracker-server.jar
