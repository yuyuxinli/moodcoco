try:
    from memu._core import hello_from_bin  # pyo3 Rust extension (optional)
except ImportError:
    hello_from_bin = None


def _rust_entry() -> str:
    """Rust entry-point verification (only available when compiled with maturin)."""
    if hello_from_bin is None:
        return "Rust extension not available (pure-Python mode)"
    return hello_from_bin()
