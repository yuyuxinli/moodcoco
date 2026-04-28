"""SJTUSkillRouter — load SJTU psych-companion SKILL.md files by name.

Scans ``MOODCOCO_SKILLS_DIR`` (default ``SJTU_skills/moodcoco-psych-companion-v1/
skills/`` relative to repo root). Each subdirectory is expected to contain a
``SKILL.md`` whose head holds a minimal YAML frontmatter block::

    ---
    name: listen
    description: 共情倾听与情绪承接...
    ---

    <markdown body>

The router exposes:

* :py:meth:`SJTUSkillRouter.list_skills` — ``{name: description}`` for every
  successfully parsed SKILL.md.
* :py:meth:`SJTUSkillRouter.load_skill_content` — full SKILL.md body (frontmatter
  block stripped) for slow_v2 system-prompt injection.

Parsing is lazy and cached on first access; rescans are not supported (build a
new router instance to re-read the directory).

Per F1 §4.6 design: malformed frontmatter is **skipped with a warning** rather
than aborting the whole scan, so one bad SKILL.md never blocks the rest of the
pack from loading. ``SkillFrontmatterError`` is reserved for callers that opt
into strict mode by parsing a single file directly.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx

logger = logging.getLogger("voice.skill_router")

_SKILLS_DIR_DEFAULT = "SJTU_skills/moodcoco-psych-companion-v1/skills"
_FRONTMATTER_DELIM = "---"


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class SkillRouterError(Exception):
    """Base class for all SJTUSkillRouter errors."""


class SkillRouterDirNotFoundError(SkillRouterError):
    """The configured skills directory does not exist or is not a directory."""


class SkillNotFoundError(SkillRouterError):
    """Requested skill name is not present in the parsed skills cache."""


class SkillFrontmatterError(SkillRouterError):
    """A SKILL.md frontmatter block is missing, malformed, or lacks required keys."""


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _resolve_skills_dir(override: Path | None) -> Path:
    """Resolve the skills directory (explicit arg → env var → default).

    Relative paths are resolved against the repo root (parent of ``backend/``).
    """
    if override is not None:
        p = Path(override).expanduser()
    else:
        env = os.getenv("MOODCOCO_SKILLS_DIR", _SKILLS_DIR_DEFAULT)
        p = Path(env).expanduser()
    if not p.is_absolute():
        # backend/voice/skill_router.py → parents[2] is repo root
        p = Path(__file__).resolve().parents[2] / p
    return p


# ---------------------------------------------------------------------------
# Frontmatter parser (no PyYAML dependency)
# ---------------------------------------------------------------------------


def _parse_skill_md(text: str) -> tuple[dict[str, str], str]:
    """Split ``SKILL.md`` text into ``(frontmatter_dict, body_without_frontmatter)``.

    Args:
        text: Raw SKILL.md content.

    Returns:
        ``(meta, body)`` where ``meta`` has at least ``name`` and ``description``
        keys when valid, and ``body`` is the markdown after the closing ``---``.

    Raises:
        SkillFrontmatterError: If the frontmatter block is missing, the closing
            delimiter is absent, or required keys (``name``, ``description``) are
            not found.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != _FRONTMATTER_DELIM:
        raise SkillFrontmatterError("missing opening '---' frontmatter delimiter")

    closing_idx: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].rstrip() == _FRONTMATTER_DELIM:
            closing_idx = idx
            break
    if closing_idx is None:
        raise SkillFrontmatterError("missing closing '---' frontmatter delimiter")

    meta: dict[str, str] = {}
    for raw in lines[1:closing_idx]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = stripped.partition(":")
        if not sep:
            # Tolerate stray lines but flag an error if it looks like a key.
            raise SkillFrontmatterError(
                f"malformed frontmatter line (no ':'): {stripped!r}"
            )
        meta[key.strip()] = value.strip().strip("'\"")

    if "name" not in meta or "description" not in meta:
        raise SkillFrontmatterError(
            "frontmatter missing required keys (name, description)"
        )

    # Body starts after the closing delimiter; drop a single leading blank line
    # so the body is not prefixed with a stray "\n".
    body_lines = lines[closing_idx + 1 :]
    if body_lines and body_lines[0].strip() == "":
        body_lines = body_lines[1:]
    body = "".join(body_lines)
    return meta, body


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class SJTUSkillRouter:
    """Lazy-loading router for SJTU psych-companion SKILL.md files.

    The router scans the skills directory once on first access (``list_skills``
    or ``load_skill_content``) and caches results for subsequent calls.

    Args:
        skills_dir: Optional explicit path. If ``None``, falls back to
            ``MOODCOCO_SKILLS_DIR`` env var, then the default repo-relative path.

    Raises:
        SkillRouterDirNotFoundError: Raised lazily on first access when the
            resolved directory does not exist.
    """

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._dir: Path = _resolve_skills_dir(skills_dir)
        self._meta: dict[str, str] = {}
        self._bodies: dict[str, str] = {}
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_skills(self) -> dict[str, str]:
        """Return ``{skill_name: description}`` for all parsed skills.

        Returns:
            New ``dict`` (caller may mutate without affecting the router cache).

        Raises:
            SkillRouterDirNotFoundError: If the configured skills directory
                does not exist.
        """
        self._ensure_loaded()
        return dict(self._meta)

    def load_skill_content(self, name: str) -> str:
        """Return the SKILL.md body (frontmatter stripped) for ``name``.

        Args:
            name: Skill name as declared in frontmatter, e.g. ``"listen"``.

        Returns:
            Markdown body text (no leading frontmatter block).

        Raises:
            SkillRouterDirNotFoundError: If the skills directory does not exist.
            SkillNotFoundError: If ``name`` is not in the parsed cache.
        """
        self._ensure_loaded()
        if name not in self._bodies:
            logger.warning(
                "skill_not_found",
                extra={
                    "session_id": voice_session_ctx.get(),
                    "turn_id": voice_turn_ctx.get(),
                    "skill_name": name,
                    "available": sorted(self._bodies.keys()),
                },
            )
            raise SkillNotFoundError(name)
        return self._bodies[name]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self._dir.exists() or not self._dir.is_dir():
            logger.error(
                "skills_dir_not_found",
                extra={
                    "session_id": voice_session_ctx.get(),
                    "turn_id": voice_turn_ctx.get(),
                    "skills_dir": str(self._dir),
                },
            )
            raise SkillRouterDirNotFoundError(str(self._dir))

        for entry in sorted(self._dir.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.is_file():
                continue
            try:
                text = skill_md.read_text(encoding="utf-8")
                meta, body = _parse_skill_md(text)
            except SkillFrontmatterError as exc:
                logger.warning(
                    "skill_frontmatter_invalid",
                    extra={
                        "session_id": voice_session_ctx.get(),
                        "turn_id": voice_turn_ctx.get(),
                        "skill_dir": entry.name,
                        "error": str(exc),
                    },
                )
                continue
            except OSError as exc:
                logger.error(
                    "skill_read_error",
                    extra={
                        "session_id": voice_session_ctx.get(),
                        "turn_id": voice_turn_ctx.get(),
                        "skill_dir": entry.name,
                        "error": str(exc),
                    },
                )
                continue

            name = meta["name"]
            self._meta[name] = meta["description"]
            self._bodies[name] = body
            logger.debug(
                "skill_loaded",
                extra={
                    "skill_name": name,
                    "content_len": len(body),
                },
            )

        self._loaded = True
        logger.info(
            "skill_router_init",
            extra={
                "skills_dir": str(self._dir),
                "skill_count": len(self._meta),
            },
        )
