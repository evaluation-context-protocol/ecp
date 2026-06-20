import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.cli import app
from typer.testing import CliRunner


class CLISmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self._manifest_tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
        self._manifest_tmp.write("manifest_version: v1\nname: test\ntarget: python agent.py\nscenarios: []\n")
        self._manifest_tmp.flush()
        self.manifest_path = self._manifest_tmp.name
        self._manifest_tmp.close()

    def _patch_runtime(self, passed: int = 1, total: int = 1):
        fake_config = object()
        fake_summary = {"passed": passed, "total": total, "scenarios": []}
        return mock.patch.multiple(
            "ecp_runtime.cli",
            _configure_logging=mock.Mock(return_value=None),
            ECPManifest=mock.Mock(from_yaml=mock.Mock(return_value=fake_config)),
            ECPRunner=mock.Mock(return_value=mock.Mock(run_scenarios=mock.Mock(return_value=fake_summary))),
        )

    def test_json_stdout_flag(self) -> None:
        with self._patch_runtime():
            result = self.runner.invoke(app, ["run", "--manifest", self.manifest_path, "--json"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["passed"], 1)
        self.assertEqual(payload["failed"], 0)

    def test_json_out_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "report.json"
            with self._patch_runtime():
                result = self.runner.invoke(
                    app, ["run", "--manifest", self.manifest_path, "--json-out", str(out_path)]
                )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue(out_path.exists())
            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("scenarios", data)

    def test_html_report_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "report.html"
            with self._patch_runtime():
                result = self.runner.invoke(
                    app, ["run", "--manifest", self.manifest_path, "--report", str(out_path)]
                )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue(out_path.exists())
            self.assertIn("ECP Evaluation Report", out_path.read_text(encoding="utf-8"))

    def test_failure_exit_code(self) -> None:
        with self._patch_runtime(passed=0, total=1):
            result = self.runner.invoke(app, ["run", "--manifest", self.manifest_path])
        self.assertEqual(result.exit_code, 2, msg=result.output)

        with self._patch_runtime(passed=0, total=1):
            result = self.runner.invoke(app, ["run", "--manifest", self.manifest_path, "--no-fail-on-error"])
        self.assertEqual(result.exit_code, 0, msg=result.output)

    def test_validate_command(self) -> None:
        result = self.runner.invoke(app, ["validate", self.manifest_path])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Manifest valid", result.output)

    def test_doctor_command(self) -> None:
        result = self.runner.invoke(app, ["doctor"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("ECP doctor", result.output)

    def test_init_command_creates_starter_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "evals"
            result = self.runner.invoke(app, ["init", str(target)])

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue((target / "agent.py").exists())
            manifest = target / "manifest.yaml"
            self.assertTrue(manifest.exists())
            self.assertIn("evaluation_context", manifest.read_text(encoding="utf-8"))

    def test_conformance_json_report(self) -> None:
        fake_agent = mock.Mock()
        fake_agent.send_rpc.side_effect = [
            {"jsonrpc": "2.0", "id": 1, "result": {"name": "test", "capabilities": {}}},
            {"jsonrpc": "2.0", "id": 2, "result": {"status": "done", "public_output": "ok"}},
            {"jsonrpc": "2.0", "id": 3, "result": True},
        ]
        fake_runtime = mock.Mock()
        fake_runtime._create_agent.return_value = fake_agent

        with mock.patch("ecp_runtime.cli.ECPRunner", return_value=fake_runtime):
            result = self.runner.invoke(app, ["conformance", "--target", "python agent.py", "--json"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["conformant"])
        self.assertEqual(payload["total"], 3)
        fake_agent.stop.assert_called_once()

    def test_conformance_rejects_invalid_step_result(self) -> None:
        fake_agent = mock.Mock()
        fake_agent.send_rpc.side_effect = [
            {"jsonrpc": "2.0", "id": 1, "result": {}},
            {"jsonrpc": "2.0", "id": 2, "result": {"status": "invalid"}},
            {"jsonrpc": "2.0", "id": 3, "result": True},
        ]
        fake_runtime = mock.Mock()
        fake_runtime._create_agent.return_value = fake_agent

        with mock.patch("ecp_runtime.cli.ECPRunner", return_value=fake_runtime):
            result = self.runner.invoke(app, ["conformance", "--target", "python agent.py"])

        self.assertEqual(result.exit_code, 1, msg=result.output)
        self.assertIn("FAIL | step result contract", result.output)


if __name__ == "__main__":
    unittest.main()
