"""CSV loaders for expert evaluation data files."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import FreeTalkScenario, SkillEvalCase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "expert_eval"
SKILLS_CASES_PATH = DATA_DIR / "skills_eval_cases.csv"
FREETALK_SCENARIOS_PATH = DATA_DIR / "freetalk_scenarios.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return [dict(row) for row in csv.DictReader(file)]


def load_skill_cases(path: Path = SKILLS_CASES_PATH) -> list[SkillEvalCase]:
    if not path.exists():
        raise FileNotFoundError(f"Missing skills eval cases file: {path}")
    return [SkillEvalCase.model_validate(row) for row in _read_csv(path)]


def load_freetalk_scenarios(
    path: Path = FREETALK_SCENARIOS_PATH,
) -> list[FreeTalkScenario]:
    if not path.exists():
        raise FileNotFoundError(f"Missing freetalk scenarios file: {path}")
    return [FreeTalkScenario.model_validate(row) for row in _read_csv(path)]
