# syntax=docker/dockerfile:1.7

FROM eclipse-temurin:21-jdk-jammy@sha256:e0c60c487345d1dc9d0fc7b6f0496f3cc941e5132e09296cc17a6decc71b902b AS build
ARG MAVEN_VERSION=3.9.16
ARG MAVEN_SHA256=5af3b743dd8b876b5c45da33b676251e5f1687712644abb4ee519ca56e1d89ce
ENV PATH="/opt/apache-maven-${MAVEN_VERSION}/bin:$PATH"
WORKDIR /workspace

RUN apt-get update \
    && apt-get install --yes --no-install-recommends curl unzip \
    && curl --fail --location --silent --show-error \
      "https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/${MAVEN_VERSION}/apache-maven-${MAVEN_VERSION}-bin.zip" \
      --output /tmp/apache-maven.zip \
    && echo "${MAVEN_SHA256}  /tmp/apache-maven.zip" | sha256sum --check --strict \
    && unzip -q /tmp/apache-maven.zip -d /opt \
    && rm -rf /tmp/apache-maven.zip /var/lib/apt/lists/*

COPY pom.xml ./
COPY src/ src/
RUN mvn --batch-mode -Dmaven.test.skip=true package

FROM eclipse-temurin:21-jre-jammy@sha256:f04fb34e053148344e83317976114ec3f37e4b830ec8bdab5a2fe3cecd7d010b AS runtime
RUN apt-get update \
    && apt-get install --yes --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 shortener \
    && useradd --system --uid 10001 --gid shortener --home-dir /app --shell /usr/sbin/nologin shortener

WORKDIR /app
COPY --from=build --chown=shortener:shortener /workspace/target/url-shortener-*.jar app.jar

USER shortener
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --start-period=20s --retries=18 \
  CMD curl --fail --silent --show-error http://localhost:8080/actuator/health/readiness || exit 1
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "/app/app.jar"]
