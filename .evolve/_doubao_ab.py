"""
Doubao A/B harness for Round 7.

Usage:
    .venv/bin/python .evolve/_doubao_ab.py <model_slug>

Runs two transcript captures with the given backend model:
    - freechat-small-win
    - skill-untangle

Logs progress to .evolve/run.log.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import time
import traceback
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / ".evolve/run.log"
FEATURES = [
    ("freechat-small-win", "transcript_doubao.md"),
    ("skill-untangle", "transcript_doubao.md"),
]


def log(step: str, result: str) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"[B] [doubao-ab] step={step} result={result}\n"
        )


def load_adapter() -> ModuleType:
    adapter_path = ROOT / ".evolve/adapter.py"
    spec = importlib.util.spec_from_file_location("evolve_adapter_doubao_ab", adapter_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load adapter spec from {adapter_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def activate_model(model_slug: str) -> None:
    os.environ["OPENAI_MODEL"] = model_slug

    llm_provider = sys.modules.get("backend.llm_provider")
    if llm_provider is not None:
        clear_cache = getattr(getattr(llm_provider, "get_openai_provider", None), "cache_clear", None)
        if clear_cache is not None:
            clear_cache()

    for module_name in [
        "backend.coordinator",
        "backend.fast",
        "backend.slow",
        "backend.llm_provider",
    ]:
        if module_name in sys.modules:
            del sys.modules[module_name]
    importlib.invalidate_caches()


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: .venv/bin/python .evolve/_doubao_ab.py <model_slug>", file=sys.stderr)
        return 2

    model_slug = sys.argv[1].strip()
    if not model_slug:
        print("model_slug must not be empty", file=sys.stderr)
        return 2

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    activate_model(model_slug)
    adapter = load_adapter()
    log("run", f"start model={model_slug}")

    setup = adapter.setup(".")
    log(
        "run",
        "setup "
        f"status={setup.get('status')} error={setup.get('error') or 'none'} model={model_slug}",
    )
    if setup.get("status") != "ready":
        return 2

    exit_code = 0
    info = setup.get("info", {})
    try:
        for feature, transcript_name in FEATURES:
            feature_dir = ROOT / ".evolve" / feature
            feature_dir.mkdir(parents=True, exist_ok=True)
            transcript_path = feature_dir / transcript_name

            t0 = time.time()
            try:
                result = adapter.run_checks(".", feature)
                details = result.get("details", "")
                transcript_path.write_text(details, encoding="utf-8")
                elapsed = time.time() - t0
                status = "error" if details.startswith("ERROR:") else "ok"
                log(
                    "run",
                    f"feature={feature} status={status} elapsed={elapsed:.1f}s "
                    f"transcript={transcript_path}",
                )
            except Exception as exc:
                elapsed = time.time() - t0
                exit_code = 1
                log(
                    "run",
                    f"feature={feature} status=crash elapsed={elapsed:.1f}s error={exc!r}",
                )
                traceback.print_exc()
    finally:
        try:
            adapter.teardown(info)
            log("run", "teardown status=ok")
        except Exception as exc:
            exit_code = 1
            log("run", f"teardown status=crash error={exc!r}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
