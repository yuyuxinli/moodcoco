from __future__ import annotations

from bestie_router import (
    SKILL_REGISTRY,
    get_all_skill_names,
    normalize_skill_name,
)


def test_all_17_canonical_skills_are_registered() -> None:
    skills = get_all_skill_names()
    assert len(skills) == 17
    assert set(skills) == set(SKILL_REGISTRY)


def test_alias_map_covers_legacy_names() -> None:
    assert normalize_skill_name("ordinary-presence") == "ambient-presence"
    assert normalize_skill_name("joyful-sharing") == "active-celebration"
    assert normalize_skill_name("playful-intimacy") == "playful-attunement"
    assert normalize_skill_name("memory-continuity") == "relationship-memory"
    assert normalize_skill_name("validation-oars") == "responsive-listening"
    assert normalize_skill_name("co-regulation") == "ground-and-regulate"
    assert normalize_skill_name("effectance-coach") == "agency-next-step"
    assert normalize_skill_name("identity-mirroring") == "identity-mirror"
    assert normalize_skill_name("relational-boundary") == "social-bridge"
    assert normalize_skill_name("autonomy-guard") == "social-bridge"
    assert normalize_skill_name("crisis-bridge") == "safety-and-crisis"
    assert normalize_skill_name("repair-and-feedback") == "rupture-repair"
    assert normalize_skill_name("decision-bestie") == "agency-next-step"


def test_contextual_aliases_disambiguate() -> None:
    assert (
        normalize_skill_name("cognitive-untangle", "他肯定不爱我")
        == "reality-soft-check"
    )
    assert (
        normalize_skill_name("cognitive-untangle", "messy issue")
        == "collaborative-untangling"
    )
    assert (
        normalize_skill_name("co-rumination-guard", "loop speculation")
        == "reality-soft-check"
    )
    assert normalize_skill_name("co-rumination-guard", "rant") == "vent-container"
    assert normalize_skill_name("belonging-repair", "现实关系") == "social-bridge"
    assert normalize_skill_name("belonging-repair", "hurt") == "responsive-listening"
