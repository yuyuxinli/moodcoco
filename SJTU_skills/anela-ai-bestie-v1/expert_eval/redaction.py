"""Secret redaction utilities for expert evaluation outputs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{8,}\b")
AUTH_BEARER_RE = re.compile(
    r"(?i)(Authorization\s*:\s*Bearer\s+)([A-Za-z0-9._\-+/=]{8,})"
)
ENV_SECRET_RE = re.compile(
    (
        r"(?im)\b((?:EXPERT_EVAL_API_KEY|MINIMAX_API_KEY|OPENAI_API_KEY|"
        r"ANELA_API_KEY|OPENROUTER_API_KEY)\s*=\s*)"
        r"(?!\[REDACTED\]|your_api_key_here)([^\s#]+)"
    )
)

_REGISTERED_SECRETS: set[str] = set()


@dataclass(frozen=True)
class SecretFinding:
    path: Path
    kind: str
    masked: str


def register_secret(secret: str | None) -> None:
    """Register a runtime secret so exact copies are removed from all outputs."""

    if secret and secret.strip() and secret.strip() not in {"your_api_key_here"}:
        _REGISTERED_SECRETS.add(secret.strip())


def mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "****"
    return f"{secret[:3]}****{secret[-4:]}"


def sanitize_text(value: Any) -> str:
    """Return a string with API keys, bearer tokens, and registered secrets redacted."""

    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)

    text = AUTH_BEARER_RE.sub(r"\1[REDACTED]", text)
    text = ENV_SECRET_RE.sub(r"\1[REDACTED]", text)
    for secret in sorted(_REGISTERED_SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, mask_secret(secret))
    text = OPENAI_KEY_RE.sub(lambda match: mask_secret(match.group(0)), text)
    return text


def sanitize_obj(value: Any) -> Any:
    """Recursively sanitize a JSON-like object."""

    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_obj(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_obj(item) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize_obj(item) for key, item in value.items()}
    return value


def sanitize_json_dumps(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(sanitize_obj(value), ensure_ascii=False, indent=indent)


def find_secret_like_text(text: str) -> list[tuple[str, str]]:
    """Find secret-like material and return masked values only."""

    findings: list[tuple[str, str]] = []
    for match in OPENAI_KEY_RE.finditer(text):
        findings.append(("openai_api_key", mask_secret(match.group(0))))
    for match in AUTH_BEARER_RE.finditer(text):
        findings.append(("authorization_bearer", "[REDACTED]"))
    for match in ENV_SECRET_RE.finditer(text):
        findings.append(("env_api_key", "[REDACTED]"))
    for secret in _REGISTERED_SECRETS:
        if secret and secret in text:
            findings.append(("registered_secret", mask_secret(secret)))
    return findings


def scan_path_for_secrets(path: Path) -> list[SecretFinding]:
    """Scan files under a path for secret-like text without returning raw secrets."""

    findings: list[SecretFinding] = []
    if not path.exists():
        return findings
    files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for kind, masked in find_secret_like_text(text):
            findings.append(SecretFinding(path=file_path, kind=kind, masked=masked))
    return findings
