"""
Frontend Journey Test adapter for Evolve skill.
Validates post-migration API responses against frontend data contracts.

No deterministic scoring — all dimensions are LLM-judged by C agent.
Setup verifies backend is running; teardown is a no-op.
"""

import socket

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

prerequisites = [
    {
        "name": "agent",
        "check": "which agent",
        "install": "Install Cursor Agent CLI from cursor.com",
        "scope": "global",
    },
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BACKEND_URL = "http://localhost:8000"
BACKEND_PORT = 8000
PSYCHOLOGISTS_ROOT = "/Users/jianghongwei/Documents/psychologists"
MOODCOCO_ROOT = "/Users/jianghongwei/Documents/moodcoco"

# ---------------------------------------------------------------------------
# Required Functions
# ---------------------------------------------------------------------------

def setup(project_dir: str) -> dict:
    """Verify backend is running at localhost:8000."""
    try:
        with socket.create_connection(("127.0.0.1", BACKEND_PORT), timeout=3):
            return {
                "status": "ready",
                "info": {
                    "backend_url": BACKEND_URL,
                    "psychologists_root": PSYCHOLOGISTS_ROOT,
                    "moodcoco_root": MOODCOCO_ROOT,
                },
                "error": None,
            }
    except (ConnectionRefusedError, OSError):
        return {
            "status": "crash",
            "info": {},
            "error": f"Backend not responding on port {BACKEND_PORT}. Run: cd {PSYCHOLOGISTS_ROOT}/backend && ./scripts/start-dev.sh",
        }


def run_checks(project_dir: str, feature: str) -> dict:
    """
    No deterministic checks — all dimensions are LLM-judged.
    Return empty scores; C agent handles all evaluation.
    """
    # Quick health check to confirm backend is still alive
    try:
        with socket.create_connection(("127.0.0.1", BACKEND_PORT), timeout=3):
            health = "backend alive"
    except (ConnectionRefusedError, OSError):
        health = "backend DOWN"

    return {
        "scores": {},
        "details": f"Feature: {feature} | {health} | All dimensions LLM-judged by C agent",
    }


def teardown(info: dict) -> None:
    """No cleanup needed — backend is managed externally."""
    pass
