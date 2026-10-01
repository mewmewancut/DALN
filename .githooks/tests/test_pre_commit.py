"""Run the real hook against a container simulator that detects npm/Vite races."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "pre-commit"


class PreCommitTests(unittest.TestCase):
    def run_hook(self, failure=""):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin"
            binary.mkdir()
            (root / "frontend_state").write_text("running")
            git = binary / "git"
            git.write_text(
                '#!/bin/sh\nif [ "$1" = rev-parse ]; then printf "%s\\n" "$HOOK_ROOT"; fi\n'
            )
            docker = binary / "docker"
            docker.write_text(
                """#!/bin/sh
echo "$*" >> "$HOOK_ROOT/calls"
case "$*" in
  *"stop frontend"*) echo stopped > "$HOOK_ROOT/frontend_state" ;;
  *"npm ci"*)
    if [ "$(cat "$HOOK_ROOT/frontend_state")" = running ]; then
      echo 'npm ci races with Vite' >&2
      exit 42
    fi
    ;;
  *"up -d"*|*"up --build -d"*) echo running > "$HOOK_ROOT/frontend_state" ;;
esac
if [ -n "$HOOK_FAILURE" ]; then
  case "$*" in *"$HOOK_FAILURE"*) exit 17 ;; esac
fi
"""
            )
            git.chmod(0o755)
            docker.chmod(0o755)
            environment = dict(
                os.environ,
                PATH=f"{binary}:{os.environ['PATH']}",
                HOOK_ROOT=str(root),
                HOOK_FAILURE=failure,
            )
            result = subprocess.run(
                ["sh", str(HOOK)],
                env=environment,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            calls = (root / "calls").read_text()
            return result, calls

    def test_dependency_install_does_not_race_with_running_frontend(self):
        result, calls = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for check in ["pytest -q", "npm test", "npm run build", "npm audit", "alembic check"]:
            self.assertIn(check, calls)
        self.assertIn("Tất cả kiểm tra đã pass", result.stdout)

    def test_failed_dependency_install_blocks_startup_and_commit(self):
        result, calls = self.run_hook("npm ci")
        self.assertEqual(result.returncode, 17)
        self.assertNotIn("up -d", calls)
        self.assertNotIn("pytest -q", calls)
        self.assertNotIn("Tất cả kiểm tra đã pass", result.stdout)

    def test_failed_tests_block_build_and_success_message(self):
        result, calls = self.run_hook("pytest -q")
        self.assertEqual(result.returncode, 17)
        self.assertNotIn("npm run build", calls)
        self.assertNotIn("Tất cả kiểm tra đã pass", result.stdout)
