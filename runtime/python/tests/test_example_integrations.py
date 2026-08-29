import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
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

    def test_async_python_demo_manifest_passes(self) -> None:
        manifest = REPO_ROOT / "examples" / "async_python_demo" / "manifest.yaml"
        result = self._run_manifest(manifest)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn('"failed": 0', result.stdout)

    def test_async_python_demo_conforms_over_http(self) -> None:
        port = self._free_port()
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        extra_paths = [str(RUNTIME_SRC), str(REPO_ROOT / "sdk" / "python" / "src")]
        if existing:
            extra_paths.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(extra_paths)
        env["ECP_TRANSPORT"] = "http"
        env["ECP_HTTP_PORT"] = str(port)

        server = subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "examples" / "async_python_demo" / "agent.py")],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        try:
            self._wait_for_port("127.0.0.1", port)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ecp_runtime.cli",
                    "conformance",
                    "--target",
                    f"http://127.0.0.1:{port}/ecp",
                    "--timeout",
                    "5",
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn('"conformant": true', result.stdout)
        finally:
            server.terminate()
            try:
                server.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate()

    def test_streamable_http_demo_manifest_passes(self) -> None:
        port = self._free_port()
        server_env = dict(os.environ)
        sdk_src = REPO_ROOT / "sdk" / "python" / "src"
        existing = server_env.get("PYTHONPATH", "")
        extra_paths = [str(sdk_src)]
        if existing:
            extra_paths.append(existing)
        server_env["PYTHONPATH"] = os.pathsep.join(extra_paths)
        server_env["ECP_HTTP_PORT"] = str(port)

        server = subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "examples" / "streamable_http_demo" / "agent.py")],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=server_env,
        )

        try:
            self._wait_for_port("127.0.0.1", port)
            with tempfile.TemporaryDirectory() as tmpdir:
                manifest_path = Path(tmpdir) / "streamable-http-manifest.yaml"
                manifest_path.write_text(
                    textwrap.dedent(
                        f"""
                        manifest_version: "v1"
                        name: "Streamable HTTP Transport Validation"
                        target: "http://127.0.0.1:{port}/ecp"

                        scenarios:
                          - name: "HTTP Echo"
                            steps:
                              - input: "echo: transport is online"
                                graders:
                                  - type: text_match
                                    field: public_output
                                    condition: contains
                                    value: "transport is online"
                                  - type: tool_usage
                                    tool_name: "http_echo"
                                    arguments:
                                      message: "transport is online"
                        """
                    ).strip(),
                    encoding="utf-8",
                )
                result = self._run_manifest(manifest_path)

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn('"failed": 0', result.stdout)
        finally:
            server.terminate()
            try:
                server.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate()

    def _free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _wait_for_port(self, host: str, port: int) -> None:
        deadline = time.time() + 5
        while time.time() < deadline:
            if self._port_is_open(host, port):
                return
            time.sleep(0.05)
        raise AssertionError(f"Timed out waiting for {host}:{port}")

    def _port_is_open(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            return False


if __name__ == "__main__":
    unittest.main()
