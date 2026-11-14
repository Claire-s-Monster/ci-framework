"""Behavioural tests for framework.actions.performance_benchmark.

Only the process boundary (subprocess.run) is replaced; detection, parsing,
regression maths, storage and the execute_benchmarks contract used by
actions/performance-benchmark/action.yml run for real against tmp_path.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from framework.actions import performance_benchmark as pb
from framework.actions.performance_benchmark import (
    BenchmarkResult,
    PerformanceBenchmarkAction,
    PerformanceMetrics,
)


def _bench(name: str, mean: float, stddev: float = 0.0) -> BenchmarkResult:
    return BenchmarkResult(
        name=name, mean=mean, stddev=stddev, min_value=mean, max_value=mean, rounds=5
    )


def _raw(name: str, mean: float) -> dict[str, Any]:
    return {
        "name": name,
        "stats": {"mean": mean, "stddev": 0.0, "min": mean, "max": mean, "rounds": 5},
    }


def _write_results(path: Path, entries: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps({"benchmarks": entries}))


class FakeRun:
    """Stand-in for subprocess.run recording calls and simulating pytest."""

    def __init__(
        self,
        entries: list[dict[str, Any]] | None = None,
        returncode: int = 0,
        write_file: bool = True,
        setup_returncode: int = 0,
    ) -> None:
        self.entries = entries if entries is not None else []
        self.returncode = returncode
        self.write_file = write_file
        self.setup_returncode = setup_returncode
        self.calls: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> SimpleNamespace:
        self.calls.append(cmd)
        self.kwargs.append(kwargs)
        if "--benchmark-only" in cmd:
            if self.write_file:
                out = Path(cmd[cmd.index("--benchmark-json") + 1])
                _write_results(out, self.entries)
            return SimpleNamespace(
                returncode=self.returncode, stdout="out", stderr="err"
            )
        return SimpleNamespace(returncode=self.setup_returncode, stdout="", stderr="")


@pytest.fixture
def action() -> PerformanceBenchmarkAction:
    return PerformanceBenchmarkAction()


@pytest.fixture
def in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """execute_benchmarks chdirs; restore cwd afterwards."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestConfig:
    def test_defaults_and_overrides_merge(self) -> None:
        a = PerformanceBenchmarkAction({"regression_threshold": 3.0, "extra": 1})
        assert a.effective_config["regression_threshold"] == 3.0
        assert a.effective_config["min_rounds"] == 5
        assert a.effective_config["extra"] == 1


class TestDetectPackageManager:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("[tool.pixi.project]\n", "pixi"),
            ("[tool.poetry]\nname='x'\n", "poetry"),
            ("[tool.hatch]\n", "hatch"),
            ("[project]\nname='x'\n", "pip"),
        ],
    )
    def test_from_pyproject(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        content: str,
        expected: str,
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(content)
        assert action.detect_package_manager(tmp_path) == expected

    def test_poetry_lock_without_pyproject(
        self, action: PerformanceBenchmarkAction, tmp_path: Path
    ) -> None:
        (tmp_path / "poetry.lock").write_text("")
        assert action.detect_package_manager(tmp_path) == "poetry"

    def test_requirements_and_empty_dir_fall_back_to_pip(
        self, action: PerformanceBenchmarkAction, tmp_path: Path
    ) -> None:
        assert action.detect_package_manager(tmp_path) == "pip"
        (tmp_path / "requirements.txt").write_text("pytest\n")
        assert action.detect_package_manager(tmp_path) == "pip"


class TestSetupEnvironment:
    def test_pixi_installs_when_import_fails(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake = FakeRun(setup_returncode=1)
        monkeypatch.setattr(pb.subprocess, "run", fake)
        assert action.setup_benchmark_environment(in_tmp, "pixi") is True
        assert fake.calls[-1] == ["pixi", "run", "pip", "install", "pytest-benchmark"]

    def test_pixi_skips_install_when_present(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake = FakeRun(setup_returncode=0)
        monkeypatch.setattr(pb.subprocess, "run", fake)
        assert action.setup_benchmark_environment(in_tmp, "pixi") is True
        assert len(fake.calls) == 1

    @pytest.mark.parametrize(
        ("manager", "expected"),
        [
            ("poetry", ["poetry", "add", "pytest-benchmark", "--group", "dev"]),
            ("pip", ["pip", "install", "pytest-benchmark"]),
        ],
    )
    def test_installs_with_manager(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
        manager: str,
        expected: list[str],
    ) -> None:
        fake = FakeRun()
        monkeypatch.setattr(pb.subprocess, "run", fake)
        assert action.setup_benchmark_environment(in_tmp, manager) is True
        assert fake.calls == [expected]
        assert fake.kwargs[0]["check"] is True

    def test_unknown_manager_is_noop_success(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake = FakeRun()
        monkeypatch.setattr(pb.subprocess, "run", fake)
        assert action.setup_benchmark_environment(in_tmp, "hatch") is True
        assert fake.calls == []

    def test_install_failure_returns_false(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def boom(cmd: list[str], **kwargs: Any) -> None:
            raise subprocess.CalledProcessError(1, cmd)

        monkeypatch.setattr(pb.subprocess, "run", boom)
        assert action.setup_benchmark_environment(in_tmp, "pip") is False
        assert "Failed to setup benchmark environment" in capsys.readouterr().out


class TestRunBenchmarks:
    @pytest.mark.parametrize(
        ("suite", "flags"),
        [
            ("quick", ["--benchmark-max-time=30", "--benchmark-min-rounds=3"]),
            ("full", ["--benchmark-max-time=300", "--benchmark-min-rounds=5"]),
            ("load", ["--benchmark-max-time=600", "--benchmark-min-rounds=10"]),
        ],
    )
    def test_suite_selects_flags_and_returns_data(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        suite: str,
        flags: list[str],
    ) -> None:
        fake = FakeRun(entries=[_raw("t", 0.5)])
        monkeypatch.setattr(pb.subprocess, "run", fake)
        ok, data = action.run_benchmarks(tmp_path, suite, "pip", 60)
        assert ok is True
        for flag in flags:
            assert flag in fake.calls[0]
        assert "-n" not in fake.calls[0]
        assert fake.kwargs[0]["cwd"] == tmp_path
        assert fake.kwargs[0]["timeout"] == 60
        assert data["benchmark_data"]["benchmarks"][0]["name"] == "t"
        assert data["stdout"] == "out"

    def test_unknown_suite_adds_no_tuning_flags(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake = FakeRun()
        monkeypatch.setattr(pb.subprocess, "run", fake)
        action.run_benchmarks(tmp_path, "custom", "pip", 10)
        assert not any(a.startswith("--benchmark-max-time") for a in fake.calls[0])

    @pytest.mark.parametrize(
        ("manager", "prefix"),
        [("pixi", ["pixi", "run"]), ("poetry", ["poetry", "run"]), ("pip", [])],
    )
    def test_wrapper_and_parallel(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        manager: str,
        prefix: list[str],
    ) -> None:
        fake = FakeRun()
        monkeypatch.setattr(pb.subprocess, "run", fake)
        action.run_benchmarks(tmp_path, "quick", manager, 10, parallel=True)
        cmd = fake.calls[0]
        assert cmd[: len(prefix)] == prefix
        assert cmd[len(prefix) : len(prefix) + 3] == ["python", "-m", "pytest"]
        assert cmd[-2:] == ["-n", "auto"]

    def test_nonzero_exit_reports_code(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(pb.subprocess, "run", FakeRun(returncode=3))
        ok, data = action.run_benchmarks(tmp_path, "quick", "pip", 10)
        assert ok is False
        assert data["error"] == "Benchmark execution failed with code 3"
        assert data["stderr"] == "err"

    def test_missing_results_file(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(pb.subprocess, "run", FakeRun(write_file=False))
        ok, data = action.run_benchmarks(tmp_path, "quick", "pip", 10)
        assert ok is False
        assert data["error"] == "No benchmark results file generated"

    def test_timeout(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def slow(cmd: list[str], **kwargs: Any) -> None:
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

        monkeypatch.setattr(pb.subprocess, "run", slow)
        ok, data = action.run_benchmarks(tmp_path, "quick", "pip", 42)
        assert ok is False
        assert data["error"] == "Benchmark execution timed out"
        assert data["execution_time"] == 42

    def test_unexpected_exception_is_contained(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def missing(cmd: list[str], **kwargs: Any) -> None:
            raise FileNotFoundError("python")

        monkeypatch.setattr(pb.subprocess, "run", missing)
        ok, data = action.run_benchmarks(tmp_path, "quick", "pip", 10)
        assert ok is False
        assert data["error"].startswith("Unexpected error:")
        assert "python" in data["error"]


class TestParseAndBaseline:
    def test_parse_maps_stats_and_defaults(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        data = {
            "benchmarks": [
                {
                    "name": "a",
                    "group": "g",
                    "fullname": "m::a",
                    "params": {"n": 1},
                    "stats": {
                        "mean": 1.5,
                        "stddev": 0.1,
                        "min": 1.0,
                        "max": 2.0,
                        "rounds": 7,
                        "ops": 0.66,
                        "data": [1.0, 2.0],
                    },
                },
                {},
            ]
        }
        a, b = action.parse_benchmark_results(data)
        assert (a.name, a.mean, a.stddev, a.min_value, a.max_value, a.rounds) == (
            "a",
            1.5,
            0.1,
            1.0,
            2.0,
            7,
        )
        assert a.group == "g"
        assert a.params == {"n": 1}
        assert a.metadata["fullname"] == "m::a"
        assert a.metadata["ops"] == 0.66
        assert a.metadata["data"] == [1.0, 2.0]
        assert (b.name, b.mean, b.rounds) == ("unknown", 0.0, 0)

    def test_parse_empty(self, action: PerformanceBenchmarkAction) -> None:
        assert action.parse_benchmark_results({}) == []

    def test_load_baseline_missing(
        self, action: PerformanceBenchmarkAction, tmp_path: Path
    ) -> None:
        assert action.load_baseline_results(tmp_path) is None

    def test_load_baseline_valid(
        self, action: PerformanceBenchmarkAction, tmp_path: Path
    ) -> None:
        _write_results(tmp_path / "benchmark-results.json", [_raw("a", 2.0)])
        loaded = action.load_baseline_results(tmp_path)
        assert loaded is not None
        assert [(r.name, r.mean) for r in loaded] == [("a", 2.0)]

    def test_load_baseline_corrupt(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (tmp_path / "benchmark-results.json").write_text("{not json")
        assert action.load_baseline_results(tmp_path) is None
        assert "Failed to load baseline results" in capsys.readouterr().out


class TestAnalyzeRegression:
    def test_regression_over_threshold(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        detected, analyses, max_pct = action.analyze_regression(
            [_bench("a", 1.5, 0.1)], [_bench("a", 1.0, 0.1)], 10.0
        )
        assert detected is True
        assert max_pct == pytest.approx(50.0)
        (an,) = analyses
        assert an.is_regression is True
        assert an.percentage_change == pytest.approx(50.0)
        assert an.effect_size == "large"
        assert an.statistical_significance == 1.0
        assert an.confidence_interval == pytest.approx((1.5 - 0.196, 1.5 + 0.196))

    def test_exactly_at_threshold_is_not_regression(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        detected, analyses, max_pct = action.analyze_regression(
            [_bench("a", 2.0)], [_bench("a", 1.0)], 100.0
        )
        assert analyses[0].percentage_change == 100.0
        assert analyses[0].is_regression is False
        assert detected is False
        assert max_pct == 0.0

    def test_medium_effect_size(self, action: PerformanceBenchmarkAction) -> None:
        _, analyses, _ = action.analyze_regression(
            [_bench("a", 1.1)], [_bench("a", 1.0)], 50.0
        )
        assert analyses[0].effect_size == "medium"

    def test_improvement_is_not_regression(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        detected, analyses, max_pct = action.analyze_regression(
            [_bench("a", 0.5)], [_bench("a", 1.0)], 10.0
        )
        assert detected is False
        assert max_pct == 0.0
        assert analyses[0].percentage_change == pytest.approx(-50.0)
        assert analyses[0].effect_size == "large"

    def test_small_effect_and_zero_variance_significance(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        _, analyses, _ = action.analyze_regression(
            [_bench("a", 1.02)], [_bench("a", 1.0)], 10.0
        )
        assert analyses[0].effect_size == "small"
        assert analyses[0].statistical_significance == 0.0

    def test_significance_scales_with_variance(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        _, analyses, _ = action.analyze_regression(
            [_bench("a", 1.2, 1.0)], [_bench("a", 1.0, 1.0)], 10.0
        )
        assert analyses[0].statistical_significance == pytest.approx(0.1)

    def test_zero_baseline_mean_gives_no_change(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        detected, analyses, _ = action.analyze_regression(
            [_bench("a", 5.0)], [_bench("a", 0.0)], 10.0
        )
        assert detected is False
        assert analyses[0].percentage_change == 0.0

    def test_unmatched_benchmarks_skipped_and_max_taken(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        detected, analyses, max_pct = action.analyze_regression(
            [_bench("a", 1.3), _bench("b", 2.0), _bench("new", 9.0)],
            [_bench("a", 1.0), _bench("b", 1.0), _bench("gone", 1.0)],
            10.0,
        )
        assert detected is True
        assert [a.benchmark_name for a in analyses] == ["a", "b"]
        assert max_pct == pytest.approx(100.0)


class TestTrendAnalysis:
    @staticmethod
    def _hist(name: str, means: list[float]) -> list[dict[str, Any]]:
        return [
            {"timestamp": i, "benchmarks": [{"name": name, "mean": m}]}
            for i, m in enumerate(means)
        ]

    def test_insufficient_data(self, action: PerformanceBenchmarkAction) -> None:
        out = action.generate_trend_analysis([_bench("a", 1.0)], self._hist("a", [1.0]))
        assert out["status"] == "insufficient_data"

    def test_degrading_improving_stable_counts(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        hist = [
            {
                "timestamp": i,
                "benchmarks": [
                    {"name": "up", "mean": 1.0 + i},
                    {"name": "down", "mean": 10.0 - i},
                    {"name": "flat", "mean": 2.0},
                ],
            }
            for i in range(3)
        ]
        current = [_bench("up", 4.0), _bench("down", 7.0), _bench("flat", 2.0)]
        out = action.generate_trend_analysis(current, hist)
        trends = out["benchmark_trends"]
        assert trends["up"]["trend_direction"] == "degrading"
        assert trends["down"]["trend_direction"] == "improving"
        assert trends["flat"]["trend_direction"] == "stable"
        assert trends["up"]["recent_trend_percentage"] == pytest.approx(50.0)
        assert trends["up"]["overall_trend_percentage"] == pytest.approx(50.0)
        assert trends["up"]["data_points"] == 3
        assert out["analysis_summary"] == {
            "total_benchmarks": 3,
            "improving_count": 1,
            "degrading_count": 1,
            "stable_count": 1,
        }

    def test_benchmark_with_one_point_excluded(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        hist = self._hist("a", [1.0, 2.0])
        out = action.generate_trend_analysis([_bench("a", 2.0), _bench("b", 1.0)], hist)
        assert list(out["benchmark_trends"]) == ["a"]

    def test_zero_mean_history_does_not_divide_by_zero(
        self, action: PerformanceBenchmarkAction
    ) -> None:
        # y_mean == 0 with non-zero slope: guarded, reported as stable.
        hist = self._hist("a", [-1.0, 1.0])
        out = action.generate_trend_analysis([_bench("a", 1.0)], hist)
        assert out["benchmark_trends"]["a"]["overall_trend_percentage"] == 0.0
        assert out["benchmark_trends"]["a"]["trend_direction"] == "stable"


class TestStoreResults:
    def test_writes_expected_document(
        self, action: PerformanceBenchmarkAction, tmp_path: Path
    ) -> None:
        metrics = PerformanceMetrics(
            benchmarks=[_bench("a", 1.5, 0.1)],
            execution_time=3.5,
            regression_detected=True,
            regression_percentage=12.5,
            environment_info={"suite": "quick"},
        )
        target = tmp_path / "nested" / "out"
        assert action.store_results(metrics, target, "quick", timestamp=1234.9) is True
        doc = json.loads((target / "benchmark-quick-1234.json").read_text())
        assert doc["timestamp"] == 1234.9
        assert doc["suite"] == "quick"
        assert doc["execution_time"] == 3.5
        assert doc["benchmarks"][0]["name"] == "a"
        assert doc["benchmarks"][0]["mean"] == 1.5
        assert doc["regression_analysis"] == {"detected": True, "percentage": 12.5}
        assert doc["environment"] == {"suite": "quick"}

    def test_default_timestamp_used(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(pb.time, "time", lambda: 999.0)
        assert action.store_results(PerformanceMetrics(), tmp_path, "full") is True
        assert (tmp_path / "benchmark-full-999.json").exists()

    def test_write_failure_returns_false(
        self,
        action: PerformanceBenchmarkAction,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A directory squatting on the target filename makes open() fail.
        (tmp_path / "benchmark-quick-5.json").mkdir()
        ok = action.store_results(PerformanceMetrics(), tmp_path, "quick", 5.0)
        assert ok is False
        assert "Failed to store results" in capsys.readouterr().out


class TestExecuteBenchmarks:
    def test_setup_failure(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def boom(cmd: list[str], **kwargs: Any) -> None:
            raise subprocess.CalledProcessError(1, cmd)

        monkeypatch.setattr(pb.subprocess, "run", boom)
        res = action.execute_benchmarks(in_tmp, results_dir=Path("res"))
        assert res["success"] is False
        assert res["benchmark_count"] == 0
        assert res["regression_detected"] is False
        assert res["baseline_comparison"] == "Environment setup failed"
        assert res["results_path"] == "res"

    def test_run_failure_propagates_error(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(pb.subprocess, "run", FakeRun(returncode=2))
        res = action.execute_benchmarks(in_tmp, suite="full", store_results=False)
        assert res["success"] is False
        assert res["suite"] == "full"
        assert res["baseline_comparison"] == "Benchmark execution failed with code 2"
        assert res["performance_report"].startswith("Benchmark execution failed:")
        assert not (in_tmp / "benchmark-results").exists()

    def test_success_without_baseline_stores_results(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            pb.subprocess, "run", FakeRun(entries=[_raw("a", 1.0), _raw("b", 2.0)])
        )
        res = action.execute_benchmarks(in_tmp, results_dir=Path("res"))
        assert res["success"] is True
        assert res["benchmark_count"] == 2
        assert res["regression_detected"] is False
        assert res["regression_percentage"] == 0.0
        assert res["baseline_comparison"] == "No baseline available"
        assert res["performance_report"] == (
            "Successfully executed 2 benchmarks without regression"
        )
        assert res["results_path"] == "res"
        (stored,) = list((in_tmp / "res").glob("benchmark-quick-*.json"))
        doc = json.loads(stored.read_text())
        assert [b["name"] for b in doc["benchmarks"]] == ["a", "b"]
        assert doc["environment"]["package_manager"] == "pip"
        assert doc["environment"]["parallel"] is False

    def test_store_results_false_writes_nothing(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(pb.subprocess, "run", FakeRun(entries=[_raw("a", 1.0)]))
        res = action.execute_benchmarks(
            in_tmp, store_results=False, results_dir=Path("res")
        )
        assert res["success"] is True
        assert not (in_tmp / "res").exists()

    def test_regression_against_baseline_detected(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base = in_tmp / "baseline-results"
        base.mkdir()
        _write_results(base / "benchmark-results.json", [_raw("a", 1.0)])
        monkeypatch.setattr(pb.subprocess, "run", FakeRun(entries=[_raw("a", 1.5)]))
        res = action.execute_benchmarks(
            in_tmp, regression_threshold=10.0, results_dir=Path("res")
        )
        assert res["success"] is True
        assert res["regression_detected"] is True
        assert res["regression_percentage"] == pytest.approx(50.0)
        assert res["baseline_comparison"] == (
            "Compared against 1 baseline benchmarks, regression detected: 50.00%"
        )
        assert res["performance_report"] == (
            "Performance regression detected: 50.00% slower than baseline"
        )
        (stored,) = list((in_tmp / "res").glob("benchmark-quick-*.json"))
        doc = json.loads(stored.read_text())
        assert doc["regression_analysis"]["detected"] is True
        assert doc["regression_analysis"]["percentage"] == pytest.approx(50.0)

    def test_threshold_decides_pass_or_fail(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base = in_tmp / "baseline-results"
        base.mkdir()
        _write_results(base / "benchmark-results.json", [_raw("a", 1.0)])
        monkeypatch.setattr(pb.subprocess, "run", FakeRun(entries=[_raw("a", 1.2)]))
        lenient = action.execute_benchmarks(
            in_tmp, regression_threshold=25.0, store_results=False
        )
        strict = action.execute_benchmarks(
            in_tmp, regression_threshold=10.0, store_results=False
        )
        assert lenient["regression_detected"] is False
        assert lenient["baseline_comparison"] == (
            "Compared against 1 baseline benchmarks, no significant regression"
        )
        assert strict["regression_detected"] is True

    def test_compare_baseline_disabled_ignores_baseline(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base = in_tmp / "baseline-results"
        base.mkdir()
        _write_results(base / "benchmark-results.json", [_raw("a", 1.0)])
        monkeypatch.setattr(pb.subprocess, "run", FakeRun(entries=[_raw("a", 9.0)]))
        res = action.execute_benchmarks(
            in_tmp, compare_baseline=False, store_results=False
        )
        assert res["regression_detected"] is False
        assert res["baseline_comparison"] == "No baseline available"

    def test_config_overrides_and_parallel_flow_through(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake = FakeRun(entries=[_raw("a", 1.0)])
        monkeypatch.setattr(pb.subprocess, "run", fake)
        res = action.execute_benchmarks(
            in_tmp,
            parallel=True,
            store_results=False,
            config_overrides={"min_rounds": 42},
        )
        assert action.effective_config["min_rounds"] == 42
        assert fake.calls[-1][-2:] == ["-n", "auto"]
        assert res["success"] is True

    def test_pixi_project_uses_pixi_wrapper(
        self,
        action: PerformanceBenchmarkAction,
        in_tmp: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (in_tmp / "pyproject.toml").write_text("[tool.pixi.workspace]\n")
        fake = FakeRun(entries=[_raw("a", 1.0)])
        monkeypatch.setattr(pb.subprocess, "run", fake)
        res = action.execute_benchmarks(in_tmp, store_results=False)
        assert res["success"] is True
        assert fake.calls[-1][:3] == ["pixi", "run", "python"]
