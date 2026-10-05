"""Small deterministic secret scanner for generated text files.

This scanner is deliberately lightweight. It catches common credential shapes and
assignment forms before a generated file is written. It never returns the matched
value, so callers can safely persist findings without copying a credential into logs.
"""

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretFinding:
    kind: str
    line: int
    fingerprint: str


class SecretScanner:
    """Detect a bounded set of credential-like values without exposing them."""

    _patterns = (
        (
            "AWS_ACCESS_KEY_ID",
            re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
        ),
        (
            "PRIVATE_KEY",
            re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        ),
        (
            "GITHUB_TOKEN",
            re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{20,}(?![A-Za-z0-9_])"),
        ),
        (
            "OPENAI_API_KEY",
            re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"),
        ),
        (
            "SECRET_ASSIGNMENT",
            re.compile(
                r"(?i)(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|password|passwd|secret)"
                r"\s*[:=]\s*['\"]?([A-Za-z0-9_+./=-]{12,})"
            ),
        ),
    )

    def scan(self, content: str) -> tuple[SecretFinding, ...]:
        findings: list[SecretFinding] = []
        for kind, pattern in self._patterns:
            for match in pattern.finditer(content):
                value = match.group(1) if match.lastindex else match.group(0)
                findings.append(
                    SecretFinding(
                        kind=kind,
                        line=content.count("\n", 0, match.start()) + 1,
                        fingerprint=hashlib.sha256(value.encode("utf-8")).hexdigest()[:16],
                    )
                )
        return tuple(
            sorted(
                set(findings), key=lambda finding: (finding.line, finding.kind, finding.fingerprint)
            )
        )
