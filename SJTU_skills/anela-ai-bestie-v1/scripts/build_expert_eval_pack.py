#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT_DIR / "dist"
PACK_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "state", "outputs")


def run(args: list[str]) -> None:
    result = subprocess.run(args, cwd=ROOT_DIR, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def read_bundle() -> dict:
    return json.loads((ROOT_DIR / "bundle.json").read_text(encoding="utf-8"))


def run_pack_self_check() -> None:
    required = [
        ROOT_DIR / "README_expert_eval.md",
        ROOT_DIR / ".env.example",
        ROOT_DIR / "requirements-expert.txt",
        ROOT_DIR / "run_expert_eval.py",
        ROOT_DIR / "run_windows.bat",
        ROOT_DIR / "run_mac.command",
        ROOT_DIR / "AGENTS.md",
        ROOT_DIR / "ROUTING.md",
        ROOT_DIR / "bundle.json",
        ROOT_DIR / "bestie_router" / "__init__.py",
        ROOT_DIR / "expert_eval" / "adapter.py",
        ROOT_DIR / "expert_eval" / "cli.py",
        ROOT_DIR / "expert_eval" / "data.py",
        ROOT_DIR / "expert_eval" / "models.py",
        ROOT_DIR / "expert_eval" / "persistence.py",
        ROOT_DIR / "expert_eval" / "redaction.py",
        ROOT_DIR / "expert_eval" / "validation.py",
        ROOT_DIR / "data" / "expert_eval" / "skills_eval_cases.csv",
        ROOT_DIR / "data" / "expert_eval" / "skills_rubric.md",
        ROOT_DIR / "data" / "expert_eval" / "freetalk_scenarios.csv",
        ROOT_DIR / "data" / "expert_eval" / "freetalk_rubric.md",
    ]
    missing = [str(path.relative_to(ROOT_DIR)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing required pack files:\n" + "\n".join(f"- {item}" for item in missing))

    with tempfile.TemporaryDirectory(prefix="anela_eval_pack_check_") as tmp:
        output_root = Path(tmp) / "outputs"
        run(
            [
                sys.executable,
                "run_expert_eval.py",
                "--mode",
                "skills",
                "--expert-id",
                "pack_self_check",
                "--output-root",
                str(output_root),
                "--dry-run",
                "--auto-score",
                "--case-id",
                "S_GE_001",
            ]
        )
        run(
            [
                sys.executable,
                "run_expert_eval.py",
                "--mode",
                "freetalk",
                "--expert-id",
                "pack_self_check",
                "--output-root",
                str(output_root),
                "--dry-run",
                "--auto-score",
                "--scenario-id",
                "FT_001",
            ]
        )
    print("Pack self-check passed.")


def copy_entry(source: Path, pack_root: Path) -> list[str]:
    relative = source.relative_to(ROOT_DIR)
    target = pack_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            ignore=PACK_IGNORE,
        )
        return sorted(str(path.relative_to(pack_root)) for path in target.rglob("*") if path.is_file())
    shutil.copy2(source, target)
    return [str(relative)]


def main() -> int:
    bundle = read_bundle()
    bundle_id = bundle["bundle_id"]
    version = bundle["version"]

    run_pack_self_check()

    pack_name = f"{bundle_id}-{version}-expert-eval-pack"
    pack_root = DIST_DIR / pack_name
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True, exist_ok=True)

    include = [
        ROOT_DIR / "README.md",
        ROOT_DIR / "AGENTS.md",
        ROOT_DIR / "ROUTING.md",
        ROOT_DIR / "bundle.json",
        ROOT_DIR / "README_expert_eval.md",
        ROOT_DIR / ".env.example",
        ROOT_DIR / "requirements-expert.txt",
        ROOT_DIR / "run_expert_eval.py",
        ROOT_DIR / "run_windows.bat",
        ROOT_DIR / "run_mac.command",
        ROOT_DIR / "bestie_router",
        ROOT_DIR / "skills",
        ROOT_DIR / "expert_eval",
        ROOT_DIR / "data" / "expert_eval",
    ]

    copied: list[str] = []
    for source in include:
        if not source.exists():
            raise SystemExit(f"Missing pack file: {source}")
        copied.extend(copy_entry(source, pack_root))

    manifest = {
        "bundle_id": bundle_id,
        "version": version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "scope": "Anela AI Friend v1 expert eval pack",
        "commands": {
            "expert_eval": "uv run --with \"pydantic>=2.7\" --with \"python-dotenv>=1.0\" python run_expert_eval.py",
            "skills": "uv run --with \"pydantic>=2.7\" --with \"python-dotenv>=1.0\" python run_expert_eval.py --mode skills",
            "freetalk": "uv run --with \"pydantic>=2.7\" --with \"python-dotenv>=1.0\" python run_expert_eval.py --mode freetalk"
        },
        "included_files": sorted(set(copied)),
    }
    (pack_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    archive = shutil.make_archive(str(pack_root), "zip", root_dir=pack_root.parent, base_dir=pack_root.name)
    shutil.rmtree(pack_root)
    print(f"Expert eval pack built: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
