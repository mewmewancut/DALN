"""Exercise the same Ruff configuration and exit codes used by pre-commit."""

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def run_ruff(arguments, source):
    return subprocess.run(
        [sys.executable, "-m", "ruff", *arguments, "--stdin-filename", "app/quality_probe.py", "-"],
        input=source,
        capture_output=True,
        text=True,
        cwd=BACKEND_ROOT,
        timeout=20,
        check=False,
    )


@pytest.mark.parametrize(
    ("source", "diagnostic"),
    [
        ("import os\n", "F401"),
        ("print(missing_price)\n", "F821"),
        ("import sys\nimport os\n\nprint(sys.version, os.name)\n", "I001"),
    ],
)
def test_ruff_rejects_invalid_code(source, diagnostic):
    result = run_ruff(["check"], source)
    assert result.returncode == 1, result.stderr
    assert diagnostic in result.stdout


def test_ruff_accepts_valid_code():
    result = run_ruff(["check"], "def total(price, quantity):\n    return price * quantity\n")
    assert result.returncode == 0, result.stdout + result.stderr


def test_ruff_format_check_rejects_bad_format_and_accepts_formatted_code():
    source = "def total( price,quantity ):return price*quantity\n"
    rejected = run_ruff(["format", "--check"], source)
    assert rejected.returncode == 1, rejected.stdout + rejected.stderr
    formatted = run_ruff(["format"], source)
    assert formatted.returncode == 0, formatted.stderr
    accepted = run_ruff(["format", "--check"], formatted.stdout)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
