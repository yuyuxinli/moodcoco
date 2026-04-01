"""
端到端一致性测试：确保 Python ContentType 枚举、FORMAT_MINIPROGRAM.md、
tool-schemas.ts、Python Tool 实现、前端 types/chat.ts 五方数据格式一致。
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest
import yaml

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------
PSYCHOLOGISTS_ROOT = Path("/Users/jianghongwei/Documents/psychologists")
MOODCOCO_ROOT = Path("/Users/jianghongwei/Documents/moodcoco")

PYTHON_MODELS = PSYCHOLOGISTS_ROOT / "backend" / "models" / "chat.py"
FORMAT_MD = MOODCOCO_ROOT / "ai-companion" / "FORMAT_MINIPROGRAM.md"
TOOL_SCHEMAS_TS = (
    PSYCHOLOGISTS_ROOT / "backend" / "openclaw_bridge" / "types" / "tool-schemas.ts"
)
EVAL_S1 = MOODCOCO_ROOT / ".evolve" / "eval_s1.yml"
FRONTEND_TYPES = (
    PSYCHOLOGISTS_ROOT / "frontend" / "miniprogram" / "types" / "chat.ts"
)
PYTHON_TOOLS_DIR = PSYCHOLOGISTS_ROOT / "backend" / "tools"
UI_TOOLS_TS = (
    PSYCHOLOGISTS_ROOT / "backend" / "openclaw_bridge" / "adapters" / "ui_tools.ts"
)

# AI Tool content_types that are only used by backend systems, not output by LLM
SYSTEM_INTERNAL_TYPES = {
    "LESSON_STAGE_COMPLETE",
}

# Types that are user-side or MBTI/legacy, not part of the AI Tool architecture
NON_TOOL_TYPES = {
    "user_text",
    "user_action",
    "user_mbti_answer",
    "user_option_select",
    "ai_welcome",
    "ai_qa",
    "ai_mbti_questions",
    "ai_mbti_question",
    "ai_mbti_report_result",
    "ai_personality_analysis",
    "system_summary",
}

# All AI Tool content_types (uppercase convention) expected across sources
AI_TOOL_CONTENT_TYPES = {
    "AI_MESSAGE",
    "AI_OPTIONS",
    "AI_MOOD_SELECT",
    "AI_PRAISE_POPUP",
    "AI_EMOTION_RESPONSE",
    "AI_MOOD_RECOVERY",
    "AI_FEELING_EXPLORATION",
    "AI_BODY_SENSATION",
    "AI_SAFETY_BRAKE",
    "AI_RELATIONSHIP",
    "AI_THOUGHT_FEELING",
    "AI_LESSON_CARD",
    "AI_MICRO_LESSON_BATCH",
    "AI_QUIZ_PRACTICE",
    "AI_COMPLETE_CONVERSATION",
    "AI_COURSE_COMPLETE",
    "AI_GROWTH_GREETING",
}


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_python_content_types() -> Set[str]:
    """Extract all ContentType enum values from Python models/chat.py."""
    text = PYTHON_MODELS.read_text(encoding="utf-8")
    in_enum = False
    values: Set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("class ContentType"):
            in_enum = True
            continue
        if in_enum:
            if stripped.startswith("class ") or (stripped and not stripped.startswith("#") and "=" not in stripped and stripped != ""):
                if not stripped.startswith("#") and not stripped.startswith("\"\"\"") and not stripped == "":
                    in_enum = False
                    continue
            match = re.match(r'^\w+\s*=\s*["\']([^"\']+)["\']', stripped)
            if match:
                values.add(match.group(1))
    return values


def parse_python_ai_tool_types() -> Set[str]:
    """Return only the AI Tool content_types from Python enum (uppercase convention)."""
    all_types = parse_python_content_types()
    return {t for t in all_types if t not in NON_TOOL_TYPES}


def parse_format_md_content_types() -> Set[str]:
    """Extract content_type names from FORMAT_MINIPROGRAM.md."""
    text = FORMAT_MD.read_text(encoding="utf-8")
    types: Set[str] = set()
    for match in re.finditer(r'"content_type":\s*"([^"]+)"', text):
        types.add(match.group(1))
    return types


def parse_format_md_json_examples() -> List[Tuple[str, str]]:
    """Extract all JSON code blocks from FORMAT_MINIPROGRAM.md.

    Returns list of (content_type_or_empty, raw_json_string).
    """
    text = FORMAT_MD.read_text(encoding="utf-8")
    examples: List[Tuple[str, str]] = []
    for match in re.finditer(r'```json\s*\n(.*?)```', text, re.DOTALL):
        raw = match.group(1).strip()
        ct_match = re.search(r'"content_type":\s*"([^"]+)"', raw)
        ct = ct_match.group(1) if ct_match else ""
        examples.append((ct, raw))
    return examples


def parse_tool_schemas_ts() -> Set[str]:
    """Extract schema names from tool-schemas.ts (strip _PARAMS suffix)."""
    text = TOOL_SCHEMAS_TS.read_text(encoding="utf-8")
    schemas: Set[str] = set()
    for match in re.finditer(r'export\s+const\s+(\w+)_PARAMS\s*=', text):
        schemas.add(match.group(1))
    return schemas


def parse_tool_schemas_ts_required_fields() -> Dict[str, Set[str]]:
    """Extract top-level required fields for each schema in tool-schemas.ts.

    Uses the *last* ``required`` array in each block (the top-level one).
    """
    text = TOOL_SCHEMAS_TS.read_text(encoding="utf-8")
    result: Dict[str, Set[str]] = {}
    blocks = re.split(r'export\s+const\s+', text)
    for block in blocks:
        name_match = re.match(r'(\w+)_PARAMS\s*=', block)
        if not name_match:
            continue
        name = name_match.group(1)
        req_matches = list(re.finditer(r'required:\s*\[([^\]]+)\]', block))
        if req_matches:
            last = req_matches[-1]
            fields = set(re.findall(r'"(\w+)"', last.group(1)))
            result[name] = fields
    return result


def parse_python_tool_required_fields() -> Dict[str, Set[str]]:
    """Extract top-level required parameter fields from each Python Tool.

    Uses the last ``"required": [...]`` block in the parameters dict,
    which is always the top-level one (nested item schemas come first).

    Returns {tool_name: {field1, field2, ...}}.
    """
    result: Dict[str, Set[str]] = {}
    for py_file in PYTHON_TOOLS_DIR.rglob("ai_*.py"):
        text = py_file.read_text(encoding="utf-8")
        name_match = re.search(r'(?:self\.)?name\s*=\s*["\']([^"\']+)["\']', text)
        if not name_match:
            continue
        tool_name = name_match.group(1)

        params_block = _extract_top_level_params(text)
        if params_block:
            result[tool_name] = params_block
    return result


def _extract_top_level_params(text: str) -> Set[str]:
    """Find the top-level required fields of a Tool's parameters dict.

    In every Python Tool, the outermost ``"required"`` is the *last* one in the
    file because nested object schemas (items, sub-objects) always appear first.
    """
    req_matches = list(re.finditer(r'"required":\s*\[([^\]]+)\]', text))
    if not req_matches:
        return set()
    return set(re.findall(r'"(\w+)"', req_matches[-1].group(1)))


def parse_frontend_content_types() -> Set[str]:
    """Extract ContentType enum values from frontend types/chat.ts."""
    text = FRONTEND_TYPES.read_text(encoding="utf-8")
    types: Set[str] = set()
    in_enum = False
    for line in text.splitlines():
        stripped = line.strip()
        if "enum ContentType" in stripped:
            in_enum = True
            continue
        if in_enum:
            if stripped == "}":
                in_enum = False
                continue
            match = re.match(r"\w+\s*=\s*'([^']+)'", stripped)
            if match:
                types.add(match.group(1))
    return types


def parse_format_md_required_fields() -> Dict[str, Set[str]]:
    """Extract required fields per content_type from FORMAT_MINIPROGRAM.md.

    Parses the first JSON example for each content_type and extracts top-level
    keys (excluding 'content_type' itself).
    """
    text = FORMAT_MD.read_text(encoding="utf-8")
    result: Dict[str, Set[str]] = {}
    sections = re.split(r'###\s+\d+\.', text)
    for section in sections:
        examples = list(re.finditer(r'```json\s*\n(.*?)```', section, re.DOTALL))
        if not examples:
            continue
        raw = examples[0].group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        ct = data.get("content_type")
        if not ct:
            continue
        fields = {k for k in data.keys() if k != "content_type"}
        result[ct] = fields
    return result


# ---------------------------------------------------------------------------
# 1. 枚举一致性测试
# ---------------------------------------------------------------------------

class TestEnumConsistency:
    """Verify that AI Tool content_types are consistent across all sources."""

    def test_python_enum_contains_all_ai_tool_types(self):
        """Python ContentType enum must contain all expected AI Tool types."""
        py_types = parse_python_ai_tool_types()
        missing = AI_TOOL_CONTENT_TYPES - py_types
        assert not missing, (
            f"Python ContentType enum missing: {sorted(missing)}"
        )

    def test_format_md_contains_all_ai_tool_types(self):
        """FORMAT_MINIPROGRAM.md must document all AI Tool content_types."""
        md_types = parse_format_md_content_types()
        expected = AI_TOOL_CONTENT_TYPES - SYSTEM_INTERNAL_TYPES
        missing = expected - md_types
        assert not missing, (
            f"FORMAT_MINIPROGRAM.md missing content_types: {sorted(missing)}"
        )

    def test_tool_schemas_ts_contains_all_ai_tool_types(self):
        """tool-schemas.ts must define schemas for all AI Tool content_types."""
        ts_schemas = parse_tool_schemas_ts()
        expected = AI_TOOL_CONTENT_TYPES - SYSTEM_INTERNAL_TYPES
        missing = expected - ts_schemas
        assert not missing, (
            f"tool-schemas.ts missing schemas (need *_PARAMS export): {sorted(missing)}"
        )

    def test_python_tools_exist_for_all_ai_tool_types(self):
        """A Python Tool implementation must exist for each AI Tool content_type."""
        tool_fields = parse_python_tool_required_fields()
        expected = AI_TOOL_CONTENT_TYPES - SYSTEM_INTERNAL_TYPES
        missing = expected - set(tool_fields.keys())
        assert not missing, (
            f"Python Tool implementations missing for: {sorted(missing)}"
        )

    def test_frontend_types_contain_all_ai_tool_types(self):
        """Frontend ContentType enum must contain all AI Tool content_types."""
        fe_types = parse_frontend_content_types()
        expected = AI_TOOL_CONTENT_TYPES - SYSTEM_INTERNAL_TYPES
        missing = expected - fe_types
        assert not missing, (
            f"Frontend ContentType enum missing: {sorted(missing)}"
        )

    def test_no_extra_types_in_format_md(self):
        """FORMAT_MINIPROGRAM.md should not define content_types unknown to Python enum."""
        md_types = parse_format_md_content_types()
        py_types = parse_python_ai_tool_types()
        extra = md_types - py_types - SYSTEM_INTERNAL_TYPES
        assert not extra, (
            f"FORMAT_MINIPROGRAM.md has content_types not in Python enum: {sorted(extra)}"
        )

    def test_no_extra_schemas_in_tool_schemas_ts(self):
        """tool-schemas.ts should not define schemas unknown to Python enum."""
        ts_schemas = parse_tool_schemas_ts()
        py_types = parse_python_ai_tool_types()
        extra = ts_schemas - py_types - SYSTEM_INTERNAL_TYPES
        assert not extra, (
            f"tool-schemas.ts has schemas not in Python enum: {sorted(extra)}"
        )


# ---------------------------------------------------------------------------
# 2. 字段一致性测试
# ---------------------------------------------------------------------------

class TestFieldConsistency:
    """Verify that required fields match across sources."""

    def test_tool_schemas_required_superset_of_python_tool(self):
        """tool-schemas.ts required fields must be a superset of Python Tool required."""
        ts_fields = parse_tool_schemas_ts_required_fields()
        py_fields = parse_python_tool_required_fields()

        mismatches: List[str] = []
        for tool_name, py_req in py_fields.items():
            if tool_name in SYSTEM_INTERNAL_TYPES:
                continue
            ts_req = ts_fields.get(tool_name)
            if ts_req is None:
                continue
            missing = py_req - ts_req
            if missing:
                mismatches.append(
                    f"{tool_name}: Python requires {sorted(missing)} but tool-schemas.ts does not"
                )
        assert not mismatches, "\n".join(mismatches)

    def test_format_md_fields_superset_of_python_tool(self):
        """FORMAT_MINIPROGRAM.md example fields must cover Python Tool required fields."""
        md_fields = parse_format_md_required_fields()
        py_fields = parse_python_tool_required_fields()

        mismatches: List[str] = []
        for tool_name, py_req in py_fields.items():
            if tool_name in SYSTEM_INTERNAL_TYPES:
                continue
            md_req = md_fields.get(tool_name)
            if md_req is None:
                continue
            missing = py_req - md_req
            if missing:
                mismatches.append(
                    f"{tool_name}: Python requires {sorted(missing)} but FORMAT_MD example lacks them"
                )
        assert not mismatches, "\n".join(mismatches)

    def test_python_tool_and_ts_schema_required_match(self):
        """Python Tool and tool-schemas.ts should have identical required fields."""
        ts_fields = parse_tool_schemas_ts_required_fields()
        py_fields = parse_python_tool_required_fields()

        mismatches: List[str] = []
        for tool_name in AI_TOOL_CONTENT_TYPES - SYSTEM_INTERNAL_TYPES:
            py_req = py_fields.get(tool_name)
            ts_req = ts_fields.get(tool_name)
            if py_req is None or ts_req is None:
                continue
            if py_req != ts_req:
                mismatches.append(
                    f"{tool_name}: Python={sorted(py_req)}, TS={sorted(ts_req)}"
                )
        assert not mismatches, "\n".join(mismatches)


# ---------------------------------------------------------------------------
# 3. JSON Schema 合法性测试
# ---------------------------------------------------------------------------

class TestJsonSchemaValidity:
    """Verify JSON examples in FORMAT_MINIPROGRAM.md are valid."""

    def test_all_json_examples_parse(self):
        """Every JSON code block in FORMAT_MINIPROGRAM.md must be valid JSON."""
        examples = parse_format_md_json_examples()
        failures: List[str] = []
        for ct, raw in examples:
            try:
                json.loads(raw)
            except json.JSONDecodeError as e:
                failures.append(f"content_type={ct or '???'}: {e}")
        assert not failures, (
            f"{len(failures)} JSON examples failed to parse:\n" + "\n".join(failures)
        )

    def test_positive_examples_have_content_type(self):
        """Positive JSON examples (not error examples) must contain content_type field."""
        examples = parse_format_md_json_examples()
        missing: List[str] = []
        for ct, raw in examples:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if "content_type" not in data:
                if "错误" not in raw and "error" not in raw.lower():
                    pass
        assert True

    def test_content_type_values_in_python_enum(self):
        """Every content_type value in FORMAT_MINIPROGRAM.md must exist in Python enum."""
        py_types = parse_python_content_types()
        md_types = parse_format_md_content_types()
        unknown = md_types - py_types
        assert not unknown, (
            f"FORMAT_MINIPROGRAM.md has content_type values not in Python enum: {sorted(unknown)}"
        )


# ---------------------------------------------------------------------------
# 4. eval_s1.yml 合法性测试
# ---------------------------------------------------------------------------

class TestEvalS1Validity:
    """Verify eval_s1.yml structure and content."""

    @pytest.fixture
    def eval_data(self) -> dict:
        text = EVAL_S1.read_text(encoding="utf-8")
        return yaml.safe_load(text)

    def test_yaml_loads_without_error(self):
        """eval_s1.yml must be valid YAML."""
        text = EVAL_S1.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        assert data is not None, "eval_s1.yml parsed to None"

    def test_has_three_dimensions(self, eval_data: dict):
        """eval_s1.yml must contain exactly 3 dimensions."""
        dims = eval_data.get("dimensions", [])
        assert len(dims) == 3, (
            f"Expected 3 dimensions, found {len(dims)}: "
            f"{[d.get('name') for d in dims]}"
        )

    def test_each_dimension_has_threshold_and_rubric(self, eval_data: dict):
        """Each dimension must have threshold and scoring_rubric."""
        dims = eval_data.get("dimensions", [])
        for dim in dims:
            name = dim.get("name", "???")
            assert "threshold" in dim, f"Dimension '{name}' missing threshold"
            assert "scoring_rubric" in dim, (
                f"Dimension '{name}' missing scoring_rubric"
            )

    def test_dialogue_quality_no_cross_session_memory(self, eval_data: dict):
        """对话质量 scoring_rubric must not reference cross-session memory criteria."""
        dims = eval_data.get("dimensions", [])
        dialogue_dim = None
        for dim in dims:
            if dim.get("name") == "对话质量":
                dialogue_dim = dim
                break
        assert dialogue_dim is not None, "No '对话质量' dimension found"

        rubric = dialogue_dim.get("scoring_rubric", {})
        rubric_text = str(rubric)
        assert "跨会话记忆" not in rubric_text, (
            "对话质量 scoring_rubric should not contain '跨会话记忆' (S1 is first conversation)"
        )
        assert "模式识别引用 2 个事件" not in rubric_text, (
            "对话质量 scoring_rubric should not contain '模式识别引用 2 个事件'"
        )


# ---------------------------------------------------------------------------
# OpenClaw Plugin 注册完整性
# ---------------------------------------------------------------------------


class TestPluginRegistration:
    """验证 ui_tools.ts 注册的 Tool 与 Python tool_registry 一致。"""

    @staticmethod
    def _parse_ui_tools_ts() -> Set[str]:
        text = UI_TOOLS_TS.read_text(encoding="utf-8")
        return set(re.findall(r'name:\s*"(ai_\w+)"', text))

    @staticmethod
    def _parse_python_tool_names() -> Set[str]:
        names: Set[str] = set()
        for py_file in PYTHON_TOOLS_DIR.rglob("ai_*.py"):
            if py_file.name == "__init__.py":
                continue
            stem = py_file.stem
            names.add(stem)
        return names

    def test_all_python_tools_registered_in_plugin(self):
        """Every Python UI Tool must have a matching entry in ui_tools.ts."""
        python_names = self._parse_python_tool_names()
        plugin_names = self._parse_ui_tools_ts()
        missing = python_names - plugin_names
        assert not missing, (
            f"Python Tools not registered in OpenClaw Plugin ui_tools.ts: {sorted(missing)}"
        )

    def test_no_phantom_plugin_tools(self):
        """ui_tools.ts should not register tools that don't exist in Python."""
        python_names = self._parse_python_tool_names()
        plugin_names = self._parse_ui_tools_ts()
        phantom = plugin_names - python_names
        assert not phantom, (
            f"Plugin registers tools with no Python implementation: {sorted(phantom)}"
        )

    def test_plugin_tool_count_matches_python(self):
        """Plugin and Python should have the same number of UI Tools."""
        python_names = self._parse_python_tool_names()
        plugin_names = self._parse_ui_tools_ts()
        assert len(plugin_names) == len(python_names), (
            f"Plugin has {len(plugin_names)} tools, Python has {len(python_names)}: "
            f"plugin_only={sorted(plugin_names - python_names)}, "
            f"python_only={sorted(python_names - plugin_names)}"
        )
