"""
ecp_runtime.trend
=================
RunTrendAnalyzer - reads a sequence of saved JSON report files produced by
``ecp run --json-out`` and computes cross-run pass-rate regression signals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Optional


@dataclass
class RunPoint:
    """Represents a single evaluation run extracted from one JSON report."""

    manifest: str
    passed: int
    total: int
    pass_rate: float


@dataclass
class RunTrendReport:
    """Aggregated analysis over a window of sequential runs."""

    window: int
    runs: List[RunPoint] = field(default_factory=list)
    pass_rate_slope: float = 0.0
    direction: Literal["improving", "degrading", "stable"] = "stable"
    any_regression: bool = False


class RunTrendAnalyzer:
    """
    Analyse cross-run pass-rate trends across a collection of JSON reports.

    The analyzer sorts report paths lexicographically and keeps only the most
    recent ``window`` reports.
    """

    _IMPROVING_THRESHOLD: float = 0.001
    _DEGRADING_THRESHOLD: float = -0.001

    def __init__(self, report_paths: List[Path], window: int = 20) -> None:
        if window < 1:
            raise ValueError(f"window must be >= 1, got {window}")
        self.report_paths: List[Path] = sorted(report_paths)[-window:]
        self.window = window

    def analyze(self) -> RunTrendReport:
        runs: List[RunPoint] = []

        for path in self.report_paths:
            point = self._load_run_point(path)
            if point is not None:
                runs.append(point)

        if len(runs) < 2:
            return RunTrendReport(
                window=self.window,
                runs=runs,
                pass_rate_slope=0.0,
                direction="stable",
                any_regression=False,
            )

        slope = self._compute_slope([run.pass_rate for run in runs])
        direction = self._classify(slope)

        return RunTrendReport(
            window=self.window,
            runs=runs,
            pass_rate_slope=round(slope, 6),
            direction=direction,
            any_regression=(direction == "degrading"),
        )

    @staticmethod
    def _load_run_point(path: Path) -> Optional[RunPoint]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        total = int(data.get("total", 0) or 0)
        passed = int(data.get("passed", 0) or 0)
        passed = max(0, min(passed, total))
        pass_rate = passed / total if total > 0 else 0.0

        return RunPoint(
            manifest=data.get("manifest", str(path)),
            passed=passed,
            total=total,
            pass_rate=pass_rate,
        )

    @staticmethod
    def _compute_slope(pass_rates: List[float]) -> float:
        count = len(pass_rates)
        if count < 2:
            return 0.0
        mean_x = (count - 1) / 2
        mean_y = sum(pass_rates) / count
        numerator = sum(
            (index - mean_x) * (rate - mean_y)
            for index, rate in enumerate(pass_rates)
        )
        denominator = sum((index - mean_x) ** 2 for index in range(count))
        return numerator / denominator if denominator else 0.0

    def _classify(self, slope: float) -> Literal["improving", "degrading", "stable"]:
        if slope > self._IMPROVING_THRESHOLD:
            return "improving"
        if slope < self._DEGRADING_THRESHOLD:
            return "degrading"
        return "stable"
