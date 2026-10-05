"""Evidence-based source impact discovery over a bounded workflow workspace."""

from dataclasses import dataclass

from app.tools.workspaces import Workspace


@dataclass(frozen=True)
class ImpactAnalysis:
    affected_files: dict[str, tuple[str, ...]]
    inspected_files: tuple[str, ...]

    @property
    def responsibilities(self) -> tuple[str, ...]:
        return tuple(sorted(self.affected_files))


class SourceImpactAnalyzer:
    """Classify actual source evidence without depending on Java class names."""

    _TEXT_SUFFIXES = (".java", ".sql", ".yaml", ".yml", ".json", ".md")

    def analyze(self, workspace: Workspace) -> ImpactAnalysis:
        inspected: list[str] = []
        affected: dict[str, list[str]] = {}
        for path in workspace.list_files():
            if not path.endswith(self._TEXT_SUFFIXES):
                continue
            content = workspace.read_file(path)
            inspected.append(path)
            normalized = content.lower()
            self._record(affected, "controller", path, "@restcontroller" in normalized)
            self._record(affected, "service", path, "@service" in normalized)
            self._record(
                affected,
                "domain_entity",
                path,
                "@entity" in normalized or (path.endswith(".java") and "/domain/" in f"/{path}"),
            )
            self._record(
                affected,
                "repository",
                path,
                "extends jparepository" in normalized or "extends crudrepository" in normalized,
            )
            self._record(
                affected,
                "redirect_behavior",
                path,
                "httpstatus.found" in normalized
                or "status.found" in normalized
                or "location(" in normalized,
            )
            self._record(
                affected,
                "migration",
                path,
                path.endswith(".sql")
                and ("create table" in normalized or "alter table" in normalized),
            )
            self._record(
                affected,
                "tests",
                path,
                path.endswith(".java") and ("@test" in normalized or "/src/test/" in f"/{path}"),
            )
            self._record(
                affected,
                "openapi_docs",
                path,
                "@operation" in normalized
                or "@apiresponse" in normalized
                or "openapi:" in normalized,
            )
        return ImpactAnalysis(
            affected_files={key: tuple(sorted(value)) for key, value in sorted(affected.items())},
            inspected_files=tuple(sorted(inspected)),
        )

    @staticmethod
    def _record(
        affected: dict[str, list[str]], responsibility: str, path: str, matched: bool
    ) -> None:
        if matched:
            affected.setdefault(responsibility, []).append(path)
