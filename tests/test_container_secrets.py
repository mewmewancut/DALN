"""Exercise Docker's real build-context rules using fake credentials only."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


class ContainerSecretTests(unittest.TestCase):
    def test_backend_image_excludes_runtime_credentials_journal_and_temporary_files(self):
        tag = f"daln-context-test-{uuid4().hex}"
        secret_names = [
            ".env", ".env.genie.json", ".env.genie.json.provision",
            ".env.genie.json.tmp", ".env.genie.json.lock",
        ]
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory)
            (context / ".dockerignore").write_bytes((ROOT / "backend/.dockerignore").read_bytes())
            for name in secret_names:
                (context / name).write_text("FAKE-CREDENTIAL-FOR-BUILD-TEST")
            (context / "genie.example.json").write_text("FAKE-EXAMPLE")
            (context / "app.py").write_text("print('test')")
            (context / "Dockerfile").write_text("FROM python:3.12-slim\nCOPY . /probe\n")
            try:
                subprocess.run(
                    ["docker", "build", "--quiet", "--tag", tag, directory],
                    check=True, capture_output=True, text=True,
                )
                check = (
                    "from pathlib import Path; p=Path('/probe'); "
                    f"assert all(not (p/n).exists() for n in {secret_names!r}); "
                    "assert (p/'app.py').exists() and (p/'genie.example.json').exists()"
                )
                subprocess.run(
                    ["docker", "run", "--rm", tag, "python", "-c", check],
                    check=True, capture_output=True, text=True,
                )
            finally:
                subprocess.run(["docker", "image", "rm", tag], capture_output=True)


if __name__ == "__main__":
    unittest.main()
