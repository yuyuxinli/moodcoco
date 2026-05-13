"""Unit tests for F7 SJTUSkillRouter.

Hermetic tests: each test builds a fake skills directory under ``tmp_path`` and
points the router at it explicitly. No SJTU real files are touched, no network
is performed, and ``MOODCOCO_SKILLS_DIR`` env state is preserved via
``monkeypatch``.

Design choice (per F1 §4.6 docstring): a malformed SKILL.md is **skipped with
a warning** during ``list_skills`` so one bad file never blocks the rest of the
pack. Strict validation is the responsibility of callers that parse a single
file directly via the private parser.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from backend.voice.skill_router import (
    SJTUSkillRouter,
    SkillFrontmatterError,
    SkillNotFoundError,
    SkillRouterDirNotFoundError,
    _parse_skill_md,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


_LISTEN_BODY = """\
# Listen

## 定义
准确理解并回应用户当下的主观体验。

## 标准动作
1. 抓住并反映情绪。
2. 不急着下结论。
"""

_CRISIS_BODY = """\
# Crisis

## 定义
检测并响应自伤、自杀、他伤等高风险线索。
"""

_VALIDATION_BODY = """\
# Validation

## 定义
让用户的体验、感受、反应被认可为可理解、可成立的。
"""


def _write_skill(skills_dir: Path, name: str, description: str, body: str) -> Path:
    """Build ``<skills_dir>/<name>/SKILL.md`` with frontmatter and body."""
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    md = skill_dir / "SKILL.md"
    md.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}",
        encoding="utf-8",
    )
    return md


@pytest.fixture
def fake_skills_dir(tmp_path: Path) -> Path:
    """Build a fake skills directory with three SKILL.md fixtures."""
    skills = tmp_path / "skills"
    skills.mkdir()
    _write_skill(
        skills,
        "listen",
        "共情倾听与情绪承接，用户带着情绪进入时优先调用。",
        _LISTEN_BODY,
    )
    _write_skill(
        skills,
        "crisis",
        "检测并响应自伤、自杀、他伤等高风险线索。",
        _CRISIS_BODY,
    )
    _write_skill(
        skills,
        "validation",
        "让用户的体验被认可为可理解、可成立的。",
        _VALIDATION_BODY,
    )
    return skills


# ---------------------------------------------------------------------------
# Tests (F1 §8 F7)
# ---------------------------------------------------------------------------


def test_list_skills_parses_frontmatter(fake_skills_dir: Path) -> None:
    """Three SKILL.md fixtures → list_skills returns 3 (name → description) entries."""
    router = SJTUSkillRouter(skills_dir=fake_skills_dir)

    skills = router.list_skills()

    assert set(skills.keys()) == {"listen", "crisis", "validation"}
    assert skills["listen"].startswith("共情倾听与情绪承接")
    assert skills["crisis"] == "检测并响应自伤、自杀、他伤等高风险线索。"
    assert skills["validation"].startswith("让用户的体验")
    # Returned dict must be a copy: mutation must not corrupt router cache.
    skills["listen"] = "MUTATED"
    assert router.list_skills()["listen"] != "MUTATED"


def test_load_skill_content_returns_body_without_frontmatter(
    fake_skills_dir: Path,
) -> None:
    """load_skill_content returns the markdown body with frontmatter stripped."""
    router = SJTUSkillRouter(skills_dir=fake_skills_dir)

    body = router.load_skill_content("listen")

    # Frontmatter delimiters and keys must be absent from the body.
    assert "---" not in body
    assert "name: listen" not in body
    assert "description:" not in body
    # Body content must be intact.
    assert body.startswith("# Listen")
    assert "准确理解并回应用户当下的主观体验" in body
    assert "不急着下结论" in body


def test_unknown_skill_raises(fake_skills_dir: Path) -> None:
    """Loading an unknown skill name raises SkillNotFoundError with the bad name."""
    router = SJTUSkillRouter(skills_dir=fake_skills_dir)

    with pytest.raises(SkillNotFoundError) as excinfo:
        router.load_skill_content("nonexistent")

    assert "nonexistent" in str(excinfo.value)


def test_dir_not_found_raises(tmp_path: Path) -> None:
    """A non-existent skills_dir raises SkillRouterDirNotFoundError on first access."""
    missing = tmp_path / "does-not-exist"
    router = SJTUSkillRouter(skills_dir=missing)

    with pytest.raises(SkillRouterDirNotFoundError) as excinfo:
        router.list_skills()
    assert str(missing) in str(excinfo.value)

    # Also fires on load_skill_content (lazy load is shared).
    router2 = SJTUSkillRouter(skills_dir=missing)
    with pytest.raises(SkillRouterDirNotFoundError):
        router2.load_skill_content("anything")


def test_malformed_frontmatter_raises_or_skips(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Malformed SKILL.md is skipped with a warning; other skills still load.

    Design (per module docstring): the router is permissive at scan time and
    logs a warning so a single bad SKILL.md cannot block the whole pack. The
    private parser still raises ``SkillFrontmatterError`` for callers that need
    strict validation on a single file.
    """
    skills = tmp_path / "skills"
    skills.mkdir()

    # Good skill — must still appear.
    _write_skill(skills, "listen", "共情倾听。", _LISTEN_BODY)

    # Malformed: missing closing ``---``.
    bad_dir = skills / "broken"
    bad_dir.mkdir()
    (bad_dir / "SKILL.md").write_text(
        "---\nname: broken\ndescription: 缺少闭合分隔符\n\n# Body without close\n",
        encoding="utf-8",
    )

    # Malformed: missing required key.
    missing_key_dir = skills / "missing-desc"
    missing_key_dir.mkdir()
    (missing_key_dir / "SKILL.md").write_text(
        "---\nname: missing-desc\n---\n\n# Body\n",
        encoding="utf-8",
    )

    router = SJTUSkillRouter(skills_dir=skills)

    with caplog.at_level(logging.WARNING, logger="voice.skill_router"):
        skills_meta = router.list_skills()

    # Only the good skill survives the scan.
    assert set(skills_meta.keys()) == {"listen"}

    # Both malformed dirs must produce a structured warning identified by record name.
    warned = [
        rec
        for rec in caplog.records
        if rec.name == "voice.skill_router"
        and rec.levelno == logging.WARNING
        and getattr(rec, "skill_dir", None) in {"broken", "missing-desc"}
    ]
    assert len(warned) == 2

    # Strict-mode parser still raises on the same input.
    with pytest.raises(SkillFrontmatterError):
        _parse_skill_md("---\nname: x\ndescription: y\n# never closes\n")
    with pytest.raises(SkillFrontmatterError):
        _parse_skill_md("---\nname: only-name\n---\n\nbody\n")
