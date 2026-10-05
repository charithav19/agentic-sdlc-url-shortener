"""Check the repository layout and bootstrap build contracts without downloads."""

import pathlib
import xml.etree.ElementTree as ET

import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIRECTORIES = (
    "apps/url-shortener/src/main/java/com/schwab/urlshortener",
    "apps/url-shortener/src/main/resources",
    "apps/url-shortener/src/test/java/com/schwab/urlshortener",
    "apps/orchestrator/app",
    "apps/orchestrator/tests",
    "apps/orchestrator/alembic/versions",
    "docs",
    "scenarios/greenfield/seed",
    "scenarios/brownfield/seed",
    "scenarios/ambiguous/seed",
    "workspaces",
    "scripts",
)
FILES = (
    "README.md",
    "Makefile",
    "docker-compose.yml",
    ".dockerignore",
    ".env.example",
    ".gitignore",
    ".editorconfig",
    "apps/url-shortener/mvnw",
    "apps/url-shortener/Dockerfile",
    "apps/url-shortener/mvnw.cmd",
    "apps/url-shortener/.mvn/wrapper/maven-wrapper.properties",
    "apps/orchestrator/uv.lock",
    "apps/orchestrator/Dockerfile",
    "scripts/health-check.sh",
    "scripts/smoke-test.sh",
    "workspaces/.gitkeep",
)


def main() -> None:
    for relative in DIRECTORIES:
        if not (ROOT / relative).is_dir():
            raise SystemExit(f"Missing directory: {relative}")
    for relative in FILES:
        if not (ROOT / relative).is_file():
            raise SystemExit(f"Missing file: {relative}")
    ns = {"m": "http://maven.apache.org/POM/4.0.0"}
    pom = ET.parse(ROOT / "apps/url-shortener/pom.xml")
    if pom.findtext("m:properties/m:java.version", namespaces=ns) != "21":
        raise SystemExit("URL service must target Java 21")
    version = pom.findtext("m:parent/m:version", namespaces=ns)
    if not version or not version.startswith("3."):
        raise SystemExit("URL service must use Spring Boot 3.x")
    with (ROOT / "apps/orchestrator/pyproject.toml").open("rb") as source:
        project = tomllib.load(source)
    if "fastapi==" not in " ".join(project["project"]["dependencies"]):
        raise SystemExit("FastAPI must be explicitly pinned")
    if not (ROOT / "apps/url-shortener/mvnw").stat().st_mode & 0o111:
        raise SystemExit("Maven wrapper must be executable")
    print(
        f"Verified {len(DIRECTORIES)} directories, {len(FILES)} files, "
        "Java 21/Spring Boot 3 and pinned FastAPI."
    )


if __name__ == "__main__":
    main()
