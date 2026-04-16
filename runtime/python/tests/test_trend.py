import json
import unittest
import tempfile
from pathlib import Path
from unittest import mock
import sys

# Ensure srd is in path for imports
RUNTIME_SRC = Path(__file__).resolve().parents[1] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from ecp_runtime.trend import RunTrendAnalyzer, RunPoint, RunTrendReport


class RunTrendAnalyzerTests(unittest.TestCase):
    def test_analyzer_handles_improving_trend(self) -> None:
        rates = [0.1, 0.5, 0.9]
        runs = [RunPoint(manifest=f"r{i}", passed=int(r*10), total=10, pass_rate=r) for i, r in enumerate(rates)]
        
        # We mock _load_run_point to avoid file IO for the core logic test
        with mock.patch.object(RunTrendAnalyzer, "_load_run_point", side_effect=runs):
            analyzer = RunTrendAnalyzer([Path("r0"), Path("r1"), Path("r2")])
            report = analyzer.analyze()
            
        self.assertEqual(report.direction, "improving")
        self.assertGreater(report.pass_rate_slope, 0.3)
        self.assertFalse(report.any_regression)

    def test_analyzer_handles_degrading_trend(self) -> None:
        rates = [0.9, 0.5, 0.1]
        runs = [RunPoint(manifest=f"r{i}", passed=int(r*10), total=10, pass_rate=r) for i, r in enumerate(rates)]
        
        with mock.patch.object(RunTrendAnalyzer, "_load_run_point", side_effect=runs):
            analyzer = RunTrendAnalyzer([Path("r0"), Path("r1"), Path("r2")])
            report = analyzer.analyze()
            
        self.assertEqual(report.direction, "degrading")
        self.assertLess(report.pass_rate_slope, -0.3)
        self.assertTrue(report.any_regression)

    def test_analyzer_handles_stable_trend(self) -> None:
        rates = [0.5, 0.50001, 0.49999]
        runs = [RunPoint(manifest=f"r{i}", passed=int(r*100), total=100, pass_rate=r) for i, r in enumerate(rates)]
        
        with mock.patch.object(RunTrendAnalyzer, "_load_run_point", side_effect=runs):
            analyzer = RunTrendAnalyzer([Path("r0"), Path("r1"), Path("r2")])
            report = analyzer.analyze()
            
        self.assertEqual(report.direction, "stable")
        self.assertAlmostEqual(report.pass_rate_slope, 0.0, places=4)
        self.assertFalse(report.any_regression)

    def test_analyzer_window_trimming(self) -> None:
        paths = [Path(f"r{i}") for i in range(10)]
        analyzer = RunTrendAnalyzer(paths, window=3)
        self.assertEqual(len(analyzer.report_paths), 3)
        self.assertEqual(analyzer.report_paths[-1].name, "r9")

    def test_single_run_returns_stable(self) -> None:
        runs = [RunPoint(manifest="r0", passed=5, total=10, pass_rate=0.5)]
        with mock.patch.object(RunTrendAnalyzer, "_load_run_point", side_effect=runs):
            analyzer = RunTrendAnalyzer([Path("r0")])
            report = analyzer.analyze()
        self.assertEqual(report.direction, "stable")
        self.assertEqual(report.pass_rate_slope, 0.0)


class RunTrendAnalyzerFileTests(unittest.TestCase):
    def test_load_run_point_from_file(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            data = {"passed": 8, "total": 10, "manifest": "test.yaml"}
            json.dump(data, tmp)
            tmp_path = Path(tmp.name)
        
        try:
            point = RunTrendAnalyzer._load_run_point(tmp_path)
            self.assertIsNotNone(point)
            self.assertEqual(point.passed, 8)
            self.assertEqual(point.pass_rate, 0.8)
            self.assertEqual(point.manifest, "test.yaml")
        finally:
            tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()
