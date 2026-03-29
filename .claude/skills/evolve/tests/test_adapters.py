"""Test adapter interface compliance for reference implementations."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from adapters import web_app, teaching


REQUIRED_FUNCTIONS = ["setup", "run_checks", "teardown"]


class TestWebAppAdapter:
    def test_has_required_functions(self):
        for fn in REQUIRED_FUNCTIONS:
            assert hasattr(web_app, fn), f"web_app missing {fn}"
            assert callable(getattr(web_app, fn))

    def test_has_prerequisites(self):
        assert hasattr(web_app, 'prerequisites')
        assert isinstance(web_app.prerequisites, list)

    def test_setup_returns_dict(self, tmp_path):
        result = web_app.setup(str(tmp_path))
        assert isinstance(result, dict)
        assert "status" in result
        assert result["status"] in ("ready", "crash")

    def test_run_checks_returns_dict(self, tmp_path):
        result = web_app.run_checks(str(tmp_path), "test_feature")
        assert isinstance(result, dict)
        assert "scores" in result
        assert "details" in result
        assert isinstance(result["scores"], dict)

    def test_teardown_accepts_dict(self):
        web_app.teardown({})
        web_app.teardown({"pid": None})

    def test_no_removed_functions(self):
        """Old interface functions should be removed."""
        removed = ["get_dimensions", "get_eval_prompt", "get_eval_output_format",
                    "get_eval_summary_format", "get_builder_instructions",
                    "get_planner_instructions", "get_prerequisite_checks"]
        for fn in removed:
            assert not hasattr(web_app, fn), f"web_app still has removed function {fn}"


class TestTeachingAdapter:
    def test_has_required_functions(self):
        for fn in REQUIRED_FUNCTIONS:
            assert hasattr(teaching, fn), f"teaching missing {fn}"
            assert callable(getattr(teaching, fn))

    def test_has_prerequisites(self):
        assert hasattr(teaching, 'prerequisites')
        assert isinstance(teaching.prerequisites, list)

    def test_setup_creates_workspace(self, tmp_path):
        result = teaching.setup(str(tmp_path))
        assert result["status"] == "ready"
        workspace = Path(result["info"]["workspace"])
        assert workspace.exists()
        assert ".evolve" in str(workspace)

    def test_run_checks_empty_scores(self, tmp_path):
        """Teaching has no deterministic scoring."""
        result = teaching.run_checks(str(tmp_path), "test_feature")
        assert result["scores"] == {}

    def test_teardown_noop(self):
        teaching.teardown({})

    def test_no_removed_functions(self):
        removed = ["get_dimensions", "get_eval_prompt", "get_eval_output_format",
                    "get_eval_summary_format", "get_builder_instructions",
                    "get_planner_instructions", "get_prerequisite_checks",
                    "get_features_from_program"]
        for fn in removed:
            assert not hasattr(teaching, fn), f"teaching still has removed function {fn}"
