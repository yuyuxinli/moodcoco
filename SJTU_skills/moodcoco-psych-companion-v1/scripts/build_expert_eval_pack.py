#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT_DIR / "expert-eval" / "runner.py"
OUTPUT_DIR = ROOT_DIR / "expert-eval" / "outputs"
REPLAY_DIR = OUTPUT_DIR / "router-replay"
DIST_DIR = ROOT_DIR / "dist"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(args: list[str]) -> None:
    result = subprocess.run(args, cwd=ROOT_DIR, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def latest_replay_artifacts() -> list[Path]:
    if not REPLAY_DIR.exists():
        return []
    grouped: dict[str, list[Path]] = {}
    for path in sorted(REPLAY_DIR.glob("*_router_replay_v2.*")):
        grouped.setdefault(path.stem, []).append(path)
    if not grouped:
        return []
    latest_stem = sorted(grouped)[-1]
    return grouped[latest_stem]


def copy_tree_entry(path: Path, pack_root: Path) -> list[str]:
    relative = path.relative_to(ROOT_DIR)
    destination = pack_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir():
        shutil.copytree(path, destination, dirs_exist_ok=True)
        return sorted(
            str(item.relative_to(pack_root))
            for item in destination.rglob("*")
            if item.is_file()
        )
    shutil.copy2(path, destination)
    return [str(relative)]


def main() -> int:
    bundle = read_json(ROOT_DIR / "bundle.json")
    bundle_id = bundle["bundle_id"]
    version = bundle["version"]

    run_command([sys.executable, str(RUNNER_PATH), "--self-check"])
    run_command([sys.executable, str(RUNNER_PATH), "--route-replay"])

    pack_name = f"{bundle_id}-{version}-expert-eval-pack"
    pack_root = DIST_DIR / pack_name
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True, exist_ok=True)

    include_paths = [
        ROOT_DIR / "AGENTS.md",
        ROOT_DIR / "README.md",
        ROOT_DIR / "ITERATION_GUIDE.md",
        ROOT_DIR / "AUTO_EVAL_CHECKLIST.md",
        ROOT_DIR / "EXPERT_EVAL_RELEASE_CHECKLIST.md",
        ROOT_DIR / "bundle.json",
        ROOT_DIR / "start_expert_eval.command",
        ROOT_DIR / "start_expert_eval.bat",
        ROOT_DIR / "skills",
        ROOT_DIR / "expert-eval" / "runner.py",
        ROOT_DIR / "expert-eval" / "cases",
        ROOT_DIR / "scripts" / "build_expert_eval_pack.py",
    ]
    include_paths.extend(latest_replay_artifacts())

    copied_files: list[str] = []
    for path in include_paths:
        if not path.exists():
            raise SystemExit(f"缺少打包文件：{path}")
        copied_files.extend(copy_tree_entry(path, pack_root))

    manifest = {
        "bundle_id": bundle_id,
        "version": version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "pack_name": pack_name,
        "scope": "MoodCoco Psych Companion V1 expert eval pack",
        "commands": {
            "self_check": "python expert-eval/runner.py --self-check",
            "route_replay": "python expert-eval/runner.py --route-replay",
            "pack": "python scripts/build_expert_eval_pack.py",
        },
        "included_files": sorted(set(copied_files)),
    }
    manifest_path = pack_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    archive_path = shutil.make_archive(str(pack_root), "zip", root_dir=pack_root.parent, base_dir=pack_root.name)
    shutil.rmtree(pack_root)
    print("专家评测包已生成：")
    print(f"- {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
