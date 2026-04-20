import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"


class ExampleIntegrationTests(unittest.TestCase):
    def _run_manifest(self, manifest_path: Path) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        extra_paths = [str(RUNTIME_SRC)]
        if existing:
            extra_paths.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(extra_paths)

        return subprocess.run(
            [
                sys.executable,
                "-m",
                "ecp_runtime.cli",
                "run",
                "--manifest",
                str(manifest_path),
                "--json",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_plain_python_demo_manifest_passes(self) -> None:
        manifest = REPO_ROOT / "examples" / "plain_python_demo" / "manifest.yaml"
        result = self._run_manifest(manifest)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn('"failed": 0', result.stdout)

    def test_two_agent_demo_manifest_passes(self) -> None:
        manifest = REPO_ROOT / "examples" / "two_agent_demo" / "manifest.yaml"
        result = self._run_manifest(manifest)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn('"failed": 0', result.stdout)


if __name__ == "__main__":
    unittest.main()
