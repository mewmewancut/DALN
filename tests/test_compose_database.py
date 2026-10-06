"""Verify the actual Compose database routing without starting containers."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ComposeDatabaseTests(unittest.TestCase):
    def configuration(self, env_file):
        environment = os.environ.copy()
        for name in ("DATABASE_URL", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
            environment.pop(name, None)
        result = subprocess.run(
            ["docker", "compose", "--env-file", str(env_file), "config", "--format", "json"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)["services"]

    def test_example_routes_to_local_database(self):
        services = self.configuration(ROOT / ".env.example")
        self.assertEqual(
            services["backend"]["environment"]["DATABASE_URL"],
            "postgresql+psycopg://fashion:fashion@db:5432/fashion",
        )

    def test_management_credential_is_only_mounted_in_optional_worker(self):
        result = subprocess.run(
            ["docker", "compose", "--env-file", str(ROOT / ".env.example"),
             "--profile", "chatbot", "config", "--format", "json"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        services = json.loads(result.stdout)["services"]
        worker = services["genie-provisioner"]
        self.assertEqual(worker["profiles"], ["chatbot"])
        self.assertEqual(worker["restart"], "unless-stopped")
        self.assertTrue(any(v["target"] == "/run/genie-worker.json" and v["read_only"]
                            for v in worker["volumes"]))
        self.assertFalse(any(v["target"] == "/run/genie-worker.json"
                             for v in services["backend"]["volumes"]))

    def test_lakebase_override_preserves_isolated_test_database(self):
        url = "postgresql+psycopg://demo:fake-password@demo.database.databricks.com:5432/fashion?sslmode=require"
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(f"DATABASE_URL={url}\n", encoding="utf-8")
            services = self.configuration(env_file)
        self.assertEqual(services["backend"]["environment"]["DATABASE_URL"], url)
        self.assertEqual(
            services["backend"]["environment"]["TEST_DATABASE_URL"],
            "postgresql+psycopg://fashion:fashion@db:5432/fashion_test",
        )

    def test_missing_url_uses_compose_postgres_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("POSTGRES_DB=demo\nPOSTGRES_USER=demo\nPOSTGRES_PASSWORD=fake\n")
            services = self.configuration(env_file)
        self.assertEqual(
            services["backend"]["environment"]["DATABASE_URL"],
            "postgresql+psycopg://demo:fake@db:5432/demo",
        )


if __name__ == "__main__":
    unittest.main()
