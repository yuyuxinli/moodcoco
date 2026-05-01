from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

IMPORT_PATHS = (
    PROJECT_ROOT / "SJTU_skills" / "anela-ai-bestie-v1",
    PROJECT_ROOT / "backend" / "skills" / "farewell" / "scripts",
    PROJECT_ROOT / "backend" / "skills" / "weekly-reflection" / "scripts",
    PROJECT_ROOT / "backend" / "skills" / "diary" / "scripts",
)

for path in IMPORT_PATHS:
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)
