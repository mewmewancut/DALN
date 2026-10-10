"""Exercise isolation with inherited fake Lakebase settings and reset failure propagation."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DemoToolingTests(unittest.TestCase):
    def test_demo_cannot_inherit_lakebase_database_or_runtime_credentials(self):
        environment = os.environ.copy()
        environment["DATABASE_URL"] = "postgresql://fake:fake@remote.example/fashion"
        environment["GENIE_CONFIG_PATH"] = "/private/fake.json"
        result = subprocess.run(
            ["docker", "compose", "--env-file", ".env.example", "-f", "compose.demo.yml",
             "--profile", "test", "config", "--format", "json"],
            cwd=ROOT, env=environment, check=True, capture_output=True, text=True,
        )
        config = json.loads(result.stdout)
        self.assertEqual(config["name"], "daln-demo")
        backend = config["services"]["backend"]
        self.assertEqual(backend["environment"]["DATABASE_URL"],
                         "postgresql+psycopg://fashion:fashion@db:5432/fashion_demo")
        self.assertNotIn("GENIE_CONFIG_PATH", backend["environment"])
        self.assertTrue(all(v["type"] == "volume" for v in backend["volumes"]))
        self.assertEqual(config["services"]["frontend"]["build"]["dockerfile"], "Dockerfile.demo")
        self.assertEqual(config["services"]["e2e"]["environment"]["E2E_API_URL"], "http://backend:8000")
        self.assertEqual(config["services"]["e2e"]["environment"]["E2E_BASE_URL"], "http://localhost")
        self.assertEqual(config["services"]["e2e"]["network_mode"], "service:frontend")
        for service in ("frontend", "backend"):
            self.assertTrue(all(p["host_ip"] == "127.0.0.1" for p in config["services"][service]["ports"]))

    def reset(self, args, failure=""):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin"
            binary.mkdir()
            docker = binary / "docker"
            docker.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$DEMO_LOG"\n'
                'if [ "$DEMO_FAIL" = reset ]; then\n'
                '  case "$*" in *"exec -T db psql"*) exit 1;; esac\n'
                'fi\n', encoding="utf-8",
            )
            docker.chmod(0o755)
            environment = os.environ.copy()
            environment.update({"PATH": str(binary) + os.pathsep + environment["PATH"],
                                "DEMO_LOG": str(root / "calls"), "DEMO_FAIL": failure})
            shell = shutil.which("sh") or "C:/Program Files/Git/bin/sh.exe"
            result = subprocess.run([shell, str(ROOT / "reset_demo.sh"), *args],
                                    env=environment, capture_output=True, text=True)
            calls = (root / "calls").read_text() if (root / "calls").exists() else ""
            return result, calls

    def test_reset_requires_exact_local_demo_confirmation_and_does_nothing_otherwise(self):
        for args in ([], ["--force"], ["--confirm-local-demo", "extra"]):
            with self.subTest(args=args):
                result, calls = self.reset(args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(calls, "")

    def test_reset_targets_only_fixed_demo_project_and_local_postgres_socket(self):
        result, calls = self.reset(["--confirm-local-demo"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all("--project-name daln-demo" in c and "-f compose.demo.yml" in c
                            for c in calls.splitlines()))
        self.assertIn("--dbname=fashion_demo", calls)
        self.assertIn("ON_ERROR_STOP=1", calls)
        self.assertNotIn("--host", calls)
        self.assertNotIn("--env-file .env ", calls)

    def test_failed_reset_blocks_startup_and_success_message(self):
        result, calls = self.reset(["--confirm-local-demo"], "reset")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("up -d --build", calls)
        self.assertNotIn("Demo đã reset", result.stdout)


if __name__ == "__main__":
    unittest.main()
