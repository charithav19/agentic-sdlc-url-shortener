FROM maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir pytest==9.1.1
COPY pom.xml /opt/warmup/pom.xml
COPY WarmupTest.java /opt/warmup/src/test/java/WarmupTest.java
RUN mvn -B -f /opt/warmup/pom.xml -Dmaven.repo.local=/opt/maven-repository package \
    && rm -rf /opt/warmup
COPY entrypoint.py /opt/runner/entrypoint.py
USER 10001:10001
WORKDIR /workspace
ENTRYPOINT ["/opt/venv/bin/python", "-I", "/opt/runner/entrypoint.py"]
