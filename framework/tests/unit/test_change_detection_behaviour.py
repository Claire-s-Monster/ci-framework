"""Behavioural tests for framework/actions/change_detection.py.

The composite action (actions/change-detection/action.yml) imports
``ChangeDetectionAction`` from this module, builds it with nine keyword
arguments and reads the analysis result.  These tests exercise that contract:
which paths are classified how, which CI jobs get skipped, which reports are
written and how failures surface.  Only the git subprocess boundary is faked;
the classification, dependency, monorepo, optimisation and report logic all run
for real against files in ``tmp_path``.
"""

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

import framework.actions.change_detection as cd
from framework.actions.change_detection import (
    ChangeAnalysisResult,
    ChangeDetectionAction,
    DependencyAnalyzer,
    FilePatternMatcher,
    MonorepoHandler,
    OptimizationEngine,
    ReportGenerator,
)


def _write(root: Path, rel: str, content: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _fake_git(
    monkeypatch: pytest.MonkeyPatch,
    stdout: str = "",
    returncode: int = 0,
    stderr: str = "",
) -> list[tuple[list[str], dict]]:
    """Replace the git subprocess boundary; return the recorded calls."""
    calls: list[tuple[list[str], dict]] = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    monkeypatch.setattr(cd.subprocess, "run", fake_run)
    return calls


def _result(**overrides) -> ChangeAnalysisResult:
    fields = {
        "success": True,
        "changed_files": ["a.py", "README.md"],
        "classifications": {"source": ["a.py"], "docs": ["README.md"]},
        "change_categories": "source,docs",
        "affected_packages": [],
        "affected_tests": [],
        "dependency_impact": 0,
        "skip_tests": False,
        "skip_security": False,
        "skip_docs": False,
        "skip_lint": False,
        "optimization_score": 0,
        "time_savings": 0,
        "execution_time": 1.234,
        "reports_path": "reports",
    }
    fields.update(overrides)
    return ChangeAnalysisResult(**fields)


# --------------------------------------------------------------------------
# FilePatternMatcher
# --------------------------------------------------------------------------


class TestFilePatternMatcher:
    @pytest.mark.parametrize(
        ("path", "category"),
        [
            ("README.md", "docs"),
            ("LICENSE", "docs"),
            ("docs/guide/intro.rst", "docs"),
            ("tests/test_a.py", "tests"),
            ("test_top.py", "tests"),
            ("src/conftest.py", "tests"),
            ("framework/tests/test_x.py", "tests"),
            ("src/app.py", "source"),
            ("framework/actions/x.py", "source"),
            ("Pipfile.lock", "dependencies"),
            ("poetry.lock", "dependencies"),
            ("yarn.lock", "dependencies"),
            ("Dockerfile", "build"),
            ("Makefile", "build"),
            ("setup.py", "build"),
            ("settings.yml", "config"),
            (".github/workflows/ci.yml", "config"),
        ],
    )
    def test_default_classification(self, path, category):
        result = FilePatternMatcher().classify_files([path])
        assert result[category] == [path]
        assert sum(len(v) for v in result.values()) == 1

    def test_extension_fallback_for_top_level_python(self):
        # "app.py" matches no glob (the source globs need a directory part),
        # so it is classified by extension.
        result = FilePatternMatcher().classify_files(["app.py", "main.go"])
        assert result["source"] == ["app.py", "main.go"]

    def test_unknown_extension_is_not_classified_anywhere(self):
        result = FilePatternMatcher().classify_files(["logo.png", "data.bin"])
        assert all(files == [] for files in result.values())

    def test_every_default_category_is_present_even_when_empty(self):
        result = FilePatternMatcher().classify_files([])
        assert set(result) == set(FilePatternMatcher.DEFAULT_PATTERNS)
        assert all(files == [] for files in result.values())

    def test_each_file_lands_in_exactly_one_category(self):
        files = ["README.md", "src/a.py", "tests/test_a.py", "Makefile", "a.toml"]
        result = FilePatternMatcher().classify_files(files)
        flat = [f for fs in result.values() for f in fs]
        assert sorted(flat) == sorted(files)

    def test_custom_patterns_override_only_named_categories(self):
        matcher = FilePatternMatcher({"docs": ["manual/**"]})
        assert matcher.patterns["docs"] == ["manual/**"]
        assert matcher.patterns["build"] == FilePatternMatcher.DEFAULT_PATTERNS["build"]
        result = matcher.classify_files(["manual/page.html", "Makefile"])
        assert result["docs"] == ["manual/page.html"]
        assert result["build"] == ["Makefile"]

    def test_custom_patterns_do_not_mutate_defaults(self):
        FilePatternMatcher({"docs": ["manual/**"]})
        assert FilePatternMatcher.DEFAULT_PATTERNS["docs"][0] == "docs/**"

    def test_custom_new_category_is_reported(self):
        matcher = FilePatternMatcher({"infra": ["terraform/**"]})
        result = matcher.classify_files(["terraform/main.tf", "src/a.py"])
        assert result["infra"] == ["terraform/main.tf"]
        assert result["source"] == ["src/a.py"]

    @pytest.mark.parametrize(
        ("file", "pattern", "expected"),
        [
            ("docs/a/b.md", "docs/**", True),
            ("other/a.md", "docs/**", False),
            ("a.md", "*.md", True),
            ("a.txt", "*.md", False),
            ("pkg/test_x.py", "**/test_*.py", True),
        ],
    )
    def test_matches_pattern(self, file, pattern, expected):
        assert FilePatternMatcher()._matches_pattern(file, pattern) is expected

    @pytest.mark.parametrize(
        ("file", "expected"),
        [
            ("a.PY", "source"),
            ("a.tsx", "source"),
            ("a.rs", "source"),
            ("a.RST", "docs"),
            ("a.ini", "config"),
            ("a.png", None),
            ("noext", None),
        ],
    )
    def test_infer_from_extension(self, file, expected):
        assert FilePatternMatcher()._infer_from_extension(file) == expected


# --------------------------------------------------------------------------
# DependencyAnalyzer
# --------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    _write(tmp_path, "pkg/__init__.py")
    _write(tmp_path, "pkg/core.py", "import os\n")
    _write(tmp_path, "pkg/util.py", "from pkg import core\nimport json\n")
    _write(tmp_path, "tests/test_core.py", "import pkg.core\n")
    _write(tmp_path, "tests/test_misc.py", "x = 1\n")
    return tmp_path


ALL_PY = [
    "pkg/__init__.py",
    "pkg/core.py",
    "pkg/util.py",
    "tests/test_core.py",
    "tests/test_misc.py",
]


class TestDependencyAnalyzer:
    def test_graph_records_only_local_imports(self, project):
        analyzer = DependencyAnalyzer(project)
        graph = analyzer.build_dependency_graph(ALL_PY)
        assert set(graph) == set(ALL_PY)
        assert graph["pkg/core.py"].imports == set()  # os is not local
        assert graph["pkg/util.py"].imports == {"pkg", "pkg.core"}
        assert graph["tests/test_core.py"].imports == {"pkg.core"}

    def test_reverse_dependencies(self, project):
        graph = DependencyAnalyzer(project).build_dependency_graph(ALL_PY)
        assert graph["pkg/core.py"].imported_by == {
            "pkg/util.py",
            "tests/test_core.py",
        }
        assert graph["pkg/util.py"].imported_by == set()

    def test_test_files_are_flagged(self, project):
        graph = DependencyAnalyzer(project).build_dependency_graph(ALL_PY)
        assert graph["tests/test_core.py"].is_test is True
        assert graph["pkg/core.py"].is_test is False

    def test_non_python_and_missing_files_are_ignored(self, project):
        graph = DependencyAnalyzer(project).build_dependency_graph(
            ["pkg/core.py", "app.js", "pkg/gone.py"]
        )
        assert set(graph) == {"pkg/core.py"}

    def test_syntax_error_file_is_kept_with_no_imports(self, project):
        _write(project, "pkg/broken.py", "def (:\n")
        graph = DependencyAnalyzer(project).build_dependency_graph(
            ["pkg/broken.py", "pkg/util.py"]
        )
        assert graph["pkg/broken.py"].imports == set()
        assert "pkg.core" in graph["pkg/util.py"].imports

    def test_one_failing_file_does_not_abort_the_rest(self, project, monkeypatch):
        analyzer = DependencyAnalyzer(project)
        original = analyzer._analyze_file_dependencies

        def flaky(file_path):
            if file_path == "pkg/util.py":
                raise RuntimeError("boom")
            return original(file_path)

        monkeypatch.setattr(analyzer, "_analyze_file_dependencies", flaky)
        graph = analyzer.build_dependency_graph(["pkg/util.py", "pkg/core.py"])
        assert set(graph) == {"pkg/core.py"}

    def test_affected_modules_include_dependents_transitively(self, tmp_path):
        _write(tmp_path, "a.py")
        _write(tmp_path, "b.py", "import a\n")
        _write(tmp_path, "c.py", "import b\n")
        _write(tmp_path, "d.py")
        analyzer = DependencyAnalyzer(tmp_path)
        analyzer.build_dependency_graph(["a.py", "b.py", "c.py", "d.py"])
        assert analyzer.get_affected_modules(["a.py"]) == {"a.py", "b.py", "c.py"}
        assert analyzer.get_affected_modules(["c.py"]) == {"c.py"}
        assert analyzer.get_affected_modules(["d.py"]) == {"d.py"}

    def test_affected_modules_ignore_files_outside_graph(self, project):
        analyzer = DependencyAnalyzer(project)
        analyzer.build_dependency_graph(ALL_PY)
        assert analyzer.get_affected_modules(["README.md", "nope.py"]) == set()

    def test_circular_imports_terminate(self, tmp_path):
        _write(tmp_path, "x.py", "import y\n")
        _write(tmp_path, "y.py", "import x\n")
        analyzer = DependencyAnalyzer(tmp_path)
        analyzer.build_dependency_graph(["x.py", "y.py"])
        assert analyzer.get_affected_modules(["x.py"]) == {"x.py", "y.py"}

    def test_affected_tests_by_naming_convention(self, project):
        analyzer = DependencyAnalyzer(project)
        analyzer.build_dependency_graph(ALL_PY)
        assert analyzer.get_affected_tests(["pkg/core.py"]) == {"tests/test_core.py"}

    def test_changed_test_file_is_always_affected(self, project):
        analyzer = DependencyAnalyzer(project)
        analyzer.build_dependency_graph(ALL_PY)
        assert analyzer.get_affected_tests(["tests/test_misc.py"]) == {
            "tests/test_misc.py"
        }

    def test_untested_module_has_no_affected_tests(self, project):
        analyzer = DependencyAnalyzer(project)
        analyzer.build_dependency_graph(ALL_PY)
        assert analyzer.get_affected_tests(["pkg/util.py"]) == set()

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("test_a.py", True),
            ("a_test.py", True),
            ("a_tests.py", True),
            ("conftest.py", True),
            ("tests/helper.py", True),
            ("pkg/test/helper.py", True),
            ("pkg/a.py", False),
            ("contest.py", False),
        ],
    )
    def test_is_test_file(self, path, expected):
        assert DependencyAnalyzer(Path("."))._is_test_file(path) is expected

    @pytest.mark.parametrize(
        ("test_file", "module_file", "expected"),
        [
            ("tests/test_core.py", "pkg/core.py", True),
            ("tests/core_test.py", "pkg/core.py", True),
            ("tests/core_tests.py", "pkg/core.py", True),
            ("tests/test_core.py", "pkg/other.py", False),
            ("tests/core.py", "pkg/core.py", True),
        ],
    )
    def test_test_matches_module(self, test_file, module_file, expected):
        analyzer = DependencyAnalyzer(Path("."))
        assert analyzer._test_matches_module(test_file, module_file) is expected

    def test_import_matches_file(self):
        analyzer = DependencyAnalyzer(Path("."))
        assert analyzer._import_matches_file("pkg.core", "pkg/core.py")
        assert analyzer._import_matches_file("pkg.core.Thing", "pkg/core.py")
        assert analyzer._import_matches_file("pkg", "pkg/__init__.py")
        assert not analyzer._import_matches_file("pkg.corex", "pkg/core.py")

    def test_local_import_detects_package_and_module(self, project):
        analyzer = DependencyAnalyzer(project)
        assert analyzer._is_local_import("pkg", "tests/test_core.py")
        assert analyzer._is_local_import("pkg.core", "tests/test_core.py")
        assert not analyzer._is_local_import("requests", "tests/test_core.py")

    def test_sibling_import_is_local_relative_to_current_dir(self, project):
        analyzer = DependencyAnalyzer(project)
        assert analyzer._is_local_import("core", "pkg/util.py")
        assert not analyzer._is_local_import("core", "tests/test_core.py")

    def test_star_imports_do_not_add_star_entries(self, tmp_path):
        _write(tmp_path, "m.py")
        _write(tmp_path, "n.py", "from m import *\n")
        imports = DependencyAnalyzer(tmp_path)._analyze_file_dependencies("n.py")
        assert imports == {"m"}

    def test_analyze_directory_path_returns_none(self, project):
        analyzer = DependencyAnalyzer(project)
        assert analyzer._analyze_file_dependencies("pkg") is None


# --------------------------------------------------------------------------
# MonorepoHandler
# --------------------------------------------------------------------------


@pytest.fixture
def monorepo(tmp_path: Path) -> Path:
    _write(tmp_path, "libA/__init__.py")
    _write(
        tmp_path,
        "libA/requirements.txt",
        "# comment\nrequests==2.0\n\nnumpy>=1.0\nscipy<=3\nattrs~=22\n",
    )
    _write(
        tmp_path,
        "libB/pyproject.toml",
        '[project]\nname = "libB"\ndependencies = ["libA>=1"]\n'
        '[tool.pixi.dependencies]\npytest = "*"\n',
    )
    _write(
        tmp_path,
        "webapp/package.json",
        json.dumps(
            {
                "dependencies": {"react": "1"},
                "devDependencies": {"jest": "1"},
                "peerDependencies": {"left-pad": "1"},
            }
        ),
    )
    _write(tmp_path, "plain/readme.txt", "no package marker")
    _write(tmp_path, ".hidden/__init__.py")
    return tmp_path


class TestMonorepoHandler:
    def test_detects_packages_and_types(self, monorepo):
        packages = MonorepoHandler(monorepo).detect_packages()
        assert set(packages) == {"libA", "libB", "webapp"}
        assert packages["libA"]["type"] == "python_package"
        assert packages["libB"]["type"] == "python_project"
        assert packages["webapp"]["type"] == "npm_package"
        assert packages["libA"]["path"] == "libA"

    def test_dependencies_are_extracted_per_package_type(self, monorepo):
        packages = MonorepoHandler(monorepo).detect_packages()
        assert packages["libA"]["dependencies"] == "requests, numpy, scipy, attrs"
        assert packages["libB"]["dependencies"] == "libA>=1, pytest"
        assert packages["webapp"]["dependencies"] == "react, jest, left-pad"

    def test_detect_packages_caches_result_on_handler(self, monorepo):
        handler = MonorepoHandler(monorepo)
        assert handler.packages == {}
        assert handler.detect_packages() is handler.packages

    def test_npm_workspaces_are_registered(self, tmp_path):
        _write(
            tmp_path,
            "package.json",
            json.dumps({"workspaces": ["packages/ui", "packages/missing"]}),
        )
        _write(
            tmp_path,
            "packages/ui/package.json",
            json.dumps({"dependencies": {"react": "1"}}),
        )
        packages = MonorepoHandler(tmp_path).detect_packages()
        assert packages["packages/ui"] == {
            "type": "npm_workspace",
            "path": "packages/ui",
            "dependencies": ["react"],
        }
        assert "packages/missing" not in packages

    def test_malformed_root_package_json_is_tolerated(self, monorepo):
        _write(monorepo, "package.json", "{not json")
        packages = MonorepoHandler(monorepo).detect_packages()
        assert set(packages) == {"libA", "libB", "webapp"}

    def test_malformed_pyproject_still_yields_package(self, tmp_path):
        _write(tmp_path, "libC/pyproject.toml", "this is [not toml")
        _write(tmp_path, "libC/requirements.txt", "flask==2\n")
        packages = MonorepoHandler(tmp_path).detect_packages()
        assert packages["libC"]["type"] == "python_project"
        assert packages["libC"]["dependencies"] == "flask"

    def test_malformed_package_json_yields_no_dependencies(self, tmp_path):
        _write(tmp_path, "web/package.json", "{{{")
        packages = MonorepoHandler(tmp_path).detect_packages()
        assert packages["web"]["dependencies"] == ""

    def test_changed_files_map_to_their_package(self, monorepo):
        handler = MonorepoHandler(monorepo)
        handler.detect_packages()
        assert handler.get_affected_packages(["webapp/src/index.js"]) == ["webapp"]

    def test_dependents_of_changed_package_are_affected(self, monorepo):
        handler = MonorepoHandler(monorepo)
        handler.detect_packages()
        affected = handler.get_affected_packages(["libA/mod.py"])
        assert sorted(affected) == ["libA", "libB"]

    def test_files_outside_any_package_affect_nothing(self, monorepo):
        handler = MonorepoHandler(monorepo)
        handler.detect_packages()
        assert handler.get_affected_packages(["README.md", "plain/readme.txt"]) == []

    def test_package_prefix_requires_directory_boundary(self, monorepo):
        handler = MonorepoHandler(monorepo)
        handler.detect_packages()
        assert handler.get_affected_packages(["libAextra/file.py"]) == []

    def test_workspace_package_changes_are_attributed(self, tmp_path):
        _write(tmp_path, "package.json", json.dumps({"workspaces": ["packages/ui"]}))
        _write(tmp_path, "packages/ui/package.json", "{}")
        handler = MonorepoHandler(tmp_path)
        handler.detect_packages()
        assert handler.get_affected_packages(["packages/ui/a.js"]) == ["packages/ui"]

    def test_dependents_of_unknown_package_is_empty(self, monorepo):
        handler = MonorepoHandler(monorepo)
        handler.detect_packages()
        assert handler._get_dependent_packages("ghost") == set()


# --------------------------------------------------------------------------
# OptimizationEngine
# --------------------------------------------------------------------------


class TestOptimizationEngine:
    def test_no_files_gives_empty_result(self):
        for classifications in ({}, {"docs": [], "source": []}):
            out = OptimizationEngine().calculate_optimization(classifications, [])
            assert out["skip_tests"] is False
            assert out["skip_security"] is False
            assert out["skip_docs"] is False
            assert out["skip_lint"] is False
            assert out["optimization_score"] == 0
            assert out["time_savings"] == 0
            assert out["reasoning"] == {"message": "No changes detected"}

    def test_docs_only_skips_tests_security_and_lint(self):
        out = OptimizationEngine().calculate_optimization({"docs": ["README.md"]}, [])
        assert out["skip_tests"] is True
        assert out["skip_security"] is True
        assert out["skip_lint"] is True
        assert out["skip_docs"] is False
        assert out["optimization_score"] == 75
        assert out["time_savings"] == 120 + 180 + 30
        assert out["change_analysis"]["docs_only"] is True

    def test_source_change_runs_everything_except_docs(self):
        out = OptimizationEngine().calculate_optimization(
            {"source": ["src/a.py"]}, ["tests/test_a.py"]
        )
        assert out["skip_tests"] is False
        assert out["skip_security"] is False
        assert out["skip_lint"] is False
        assert out["skip_docs"] is True
        assert out["optimization_score"] == 25
        assert out["time_savings"] == 60
        assert out["affected_tests"] == ["tests/test_a.py"]

    def test_config_only_skips_security_but_not_lint(self):
        out = OptimizationEngine().calculate_optimization({"config": ["a.yml"]}, [])
        assert out["skip_tests"] is True
        assert out["skip_security"] is True
        assert out["skip_lint"] is False
        assert out["skip_docs"] is True
        assert out["optimization_score"] == 75
        assert out["time_savings"] == 120 + 180 + 60
        assert out["change_analysis"]["config_only"] is True

    def test_config_with_source_requires_security_scan(self):
        out = OptimizationEngine().calculate_optimization(
            {"config": ["a.yml"], "source": ["src/a.py"]}, []
        )
        assert out["skip_security"] is False
        assert out["skip_tests"] is False

    def test_dependency_change_blocks_skipping_tests_and_security(self):
        out = OptimizationEngine().calculate_optimization(
            {"dependencies": ["poetry.lock"], "config": ["a.yml"]}, []
        )
        assert out["skip_tests"] is False
        assert out["skip_security"] is False

    def test_tests_only_change_still_runs_tests(self):
        out = OptimizationEngine().calculate_optimization(
            {"tests": ["tests/test_a.py"]}, []
        )
        assert out["change_analysis"]["tests_only"] is True
        assert out["skip_tests"] is False

    def test_ci_only_pattern_detected(self):
        out = OptimizationEngine().calculate_optimization({"ci": ["x"]}, [])
        assert out["change_analysis"]["ci_only"] is True

    def test_disabling_job_skipping_keeps_all_jobs_but_tests_follow_own_flag(self):
        out = OptimizationEngine(
            enable_test_optimization=True, enable_job_skipping=False
        ).calculate_optimization({"docs": ["README.md"]}, [])
        assert out["skip_security"] is False
        assert out["skip_docs"] is False
        assert out["skip_lint"] is False
        assert out["skip_tests"] is True
        assert out["optimization_score"] == 25
        assert out["time_savings"] == 120

    def test_disabling_test_optimization_never_skips_tests(self):
        out = OptimizationEngine(enable_test_optimization=False).calculate_optimization(
            {"docs": ["README.md"]}, []
        )
        assert out["skip_tests"] is False
        assert out["skip_security"] is True
        assert out["optimization_score"] == 50

    def test_reasoning_explains_each_decision(self):
        docs = OptimizationEngine().calculate_optimization({"docs": ["README.md"]}, [])[
            "reasoning"
        ]
        assert docs["tests"] == "No source, test, or dependency changes"
        assert docs["lint"] == "Only documentation changes"
        src = OptimizationEngine().calculate_optimization({"source": ["a.py"]}, [])[
            "reasoning"
        ]
        assert src["tests"] == "Source/test/dependency changes detected"
        assert src["docs"] == "No documentation changes"
        assert src["security"] == "Source/dependency changes require security scan"


# --------------------------------------------------------------------------
# ReportGenerator
# --------------------------------------------------------------------------


class TestReportGenerator:
    def test_creates_nested_reports_dir(self, tmp_path):
        target = tmp_path / "a" / "b" / "reports"
        ReportGenerator(target)
        assert target.is_dir()

    def test_generates_three_reports_and_returns_json_path(self, tmp_path):
        gen = ReportGenerator(tmp_path / "r")
        returned = gen.generate_reports(_result())
        assert returned == str(tmp_path / "r" / "change-detection-report.json")
        for name in (
            "change-detection-report.json",
            "change-detection-summary.md",
            "change-detection-detailed.md",
        ):
            assert (tmp_path / "r" / name).is_file()

    def test_json_report_round_trips_result_and_extra_data(self, tmp_path):
        gen = ReportGenerator(tmp_path)
        result = _result(optimization_score=75, time_savings=330)
        gen.generate_reports(result, {"change_analysis": {"docs_only": True}})
        data = json.loads((tmp_path / "change-detection-report.json").read_text())
        for key, value in asdict(result).items():
            assert data[key] == value
        assert data["change_analysis"] == {"docs_only": True}
        assert data["metadata"]["generator"] == "change-detection-action"
        assert data["metadata"]["version"] == "0.0.1"
        assert data["metadata"]["timestamp"].endswith("Z")

    def test_markdown_summary_with_savings(self, tmp_path):
        gen = ReportGenerator(tmp_path)
        gen.generate_reports(
            _result(
                skip_tests=True,
                skip_security=True,
                skip_docs=True,
                skip_lint=True,
                optimization_score=100,
                time_savings=390,
                affected_tests=["tests/test_a.py"],
                affected_packages=["libA"],
            )
        )
        md = (tmp_path / "change-detection-summary.md").read_text(encoding="utf-8")
        assert "- **Files Changed:** 2" in md
        assert "- **Optimization Score:** 100%" in md
        assert "- **Estimated Time Savings:** 390s" in md
        assert "- **Analysis Time:** 1.23s" in md
        assert "**100% of CI pipeline can be optimized!**" in md
        assert "**Skip Tests:**" in md
        assert "**Skip Security Scans:**" in md
        assert "**Skip Documentation Build:**" in md
        assert "**Skip Linting:**" in md
        assert "**Estimated time savings: 390 seconds**" in md
        assert "- `tests/test_a.py`" in md
        assert "- `libA`" in md
        assert "pytest ${{ steps.change-detection.outputs.affected-tests }}" in md
        assert "- **Source:** 1 files" in md
        assert "  - `a.py`" in md

    def test_markdown_summary_without_savings(self, tmp_path):
        ReportGenerator(tmp_path).generate_reports(_result())
        md = (tmp_path / "change-detection-summary.md").read_text(encoding="utf-8")
        assert "Full CI Pipeline Required" in md
        assert "can be optimized" not in md
        assert "Affected Tests" not in md
        assert "Affected Packages" not in md
        assert "        run: pytest\n" in md

    def test_markdown_only_lists_enabled_skips(self, tmp_path):
        ReportGenerator(tmp_path).generate_reports(
            _result(skip_docs=True, optimization_score=25, time_savings=60)
        )
        md = (tmp_path / "change-detection-summary.md").read_text(encoding="utf-8")
        assert "**Skip Documentation Build:**" in md
        assert "**Skip Tests:**" not in md
        assert "**Skip Linting:**" not in md

    def test_markdown_truncates_long_affected_test_list(self, tmp_path):
        tests = [f"tests/test_{i:02d}.py" for i in range(25)]
        ReportGenerator(tmp_path).generate_reports(_result(affected_tests=tests))
        md = (tmp_path / "change-detection-summary.md").read_text(encoding="utf-8")
        assert "- `tests/test_19.py`" in md
        assert "tests/test_20.py" not in md
        assert "... and 5 more tests" in md

    def test_markdown_omits_empty_categories(self, tmp_path):
        ReportGenerator(tmp_path).generate_reports(
            _result(classifications={"source": ["a.py"], "docs": []})
        )
        md = (tmp_path / "change-detection-summary.md").read_text(encoding="utf-8")
        assert "**Source:**" in md
        assert "**Docs:**" not in md

    def test_no_category_section_when_categories_blank(self, tmp_path):
        ReportGenerator(tmp_path).generate_reports(_result(change_categories=""))
        md = (tmp_path / "change-detection-summary.md").read_text(encoding="utf-8")
        assert "Change Categories" not in md

    def test_detailed_report_lists_files_and_extra_sections(self, tmp_path):
        extra = {
            "dependency_graph": {"a.py": {}, "b.py": {}},
            "optimization_reasoning": {"tests": "because", "docs": "reasons"},
        }
        ReportGenerator(tmp_path).generate_reports(_result(dependency_impact=2), extra)
        text = (tmp_path / "change-detection-detailed.md").read_text(encoding="utf-8")
        assert "### Source Files" in text
        assert "- `a.py`" in text
        assert "### Docs Files" in text
        assert "**Total modules analyzed:** 2" in text
        assert "**Modules with dependencies:** 2" in text
        assert "- **Tests:** because" in text
        assert "- **Docs:** reasons" in text
        assert "**Files processed:** 2" in text
        assert "**Categories identified:** 2" in text

    def test_detailed_report_without_extra_data_skips_optional_sections(self, tmp_path):
        ReportGenerator(tmp_path).generate_reports(_result())
        text = (tmp_path / "change-detection-detailed.md").read_text(encoding="utf-8")
        assert "Dependency Analysis" not in text
        assert "Optimization Reasoning" not in text
        assert "Performance Metrics" in text


# --------------------------------------------------------------------------
# ChangeDetectionAction: construction and the action.yml contract
# --------------------------------------------------------------------------


class TestActionConstruction:
    def test_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        action = ChangeDetectionAction()
        assert action.project_dir == Path.cwd()
        assert action.reports_dir == Path.cwd() / "change-reports"
        assert action.reports_dir.is_dir()
        assert action.detection_level == "standard"
        assert action.base_ref == "HEAD~1"
        assert action.head_ref == "HEAD"
        assert action.enable_test_optimization is True
        assert action.enable_job_skipping is True
        assert action.monorepo_mode is False
        assert action.monorepo_handler is None

    def test_accepts_the_nine_keywords_action_yml_passes(self, tmp_path):
        action = ChangeDetectionAction(
            project_dir=tmp_path,
            reports_dir=tmp_path / "out",
            detection_level="quick",
            base_ref="origin/main",
            head_ref="feature",
            enable_test_optimization=False,
            enable_job_skipping=False,
            monorepo_mode=True,
            pattern_config=None,
        )
        assert action.reports_dir == tmp_path / "out"
        assert action.detection_level == "quick"
        assert (action.base_ref, action.head_ref) == ("origin/main", "feature")
        assert action.optimization_engine.enable_test_optimization is False
        assert action.optimization_engine.enable_job_skipping is False
        assert isinstance(action.monorepo_handler, MonorepoHandler)

    def test_result_exposes_every_field_action_yml_reads(self, tmp_path):
        # action.yml reads these names from the result to emit step outputs.
        action = ChangeDetectionAction(project_dir=tmp_path)
        fields = asdict(action._create_empty_result(0.5))
        for name in (
            "success",
            "execution_time",
            "changed_files",
            "change_categories",
            "affected_packages",
            "skip_tests",
            "skip_security",
            "skip_docs",
            "skip_lint",
            "optimization_score",
            "time_savings",
            "affected_tests",
            "dependency_impact",
            "reports_path",
            "failure_reason",
        ):
            assert name in fields
        assert ",".join(fields["changed_files"]) == ""


class TestPatternConfig:
    def test_json_config_overrides_named_category(self, tmp_path):
        _write(
            tmp_path,
            "patterns.json",
            json.dumps({"patterns": {"docs": ["manual/**"]}}),
        )
        action = ChangeDetectionAction(
            project_dir=tmp_path, pattern_config="patterns.json"
        )
        assert action.pattern_matcher.patterns["docs"] == ["manual/**"]
        assert (
            action.pattern_matcher.patterns["build"]
            == FilePatternMatcher.DEFAULT_PATTERNS["build"]
        )

    def test_toml_config_is_supported(self, tmp_path):
        _write(tmp_path, "patterns.toml", '[patterns]\ninfra = ["terraform/**"]\n')
        action = ChangeDetectionAction(
            project_dir=tmp_path, pattern_config="patterns.toml"
        )
        assert action.pattern_matcher.patterns["infra"] == ["terraform/**"]

    @pytest.mark.parametrize(
        ("name", "content"),
        [
            ("missing.json", None),
            ("patterns.yaml", "patterns: {}\n"),
            ("broken.json", "{nope"),
            ("broken.toml", "[[[bad"),
        ],
    )
    def test_unusable_config_falls_back_to_defaults(self, tmp_path, name, content):
        if content is not None:
            _write(tmp_path, name, content)
        action = ChangeDetectionAction(project_dir=tmp_path, pattern_config=name)
        assert action.pattern_matcher.patterns == FilePatternMatcher.DEFAULT_PATTERNS

    def test_empty_pattern_config_uses_defaults(self, tmp_path):
        action = ChangeDetectionAction(project_dir=tmp_path, pattern_config="")
        assert action.pattern_matcher.patterns == FilePatternMatcher.DEFAULT_PATTERNS


# --------------------------------------------------------------------------
# ChangeDetectionAction._get_changed_files
# --------------------------------------------------------------------------


class TestGetChangedFiles:
    def test_runs_three_dot_diff_in_project_dir(self, tmp_path, monkeypatch):
        calls = _fake_git(monkeypatch, stdout="a.py\n\n  b.md  \n")
        action = ChangeDetectionAction(
            project_dir=tmp_path, base_ref="origin/main", head_ref="feat"
        )
        assert action._get_changed_files() == ["a.py", "b.md"]
        cmd, kwargs = calls[0]
        assert cmd == ["git", "diff", "--name-only", "origin/main...feat"]
        assert kwargs["cwd"] == tmp_path

    def test_nonzero_exit_means_no_changes(self, tmp_path, monkeypatch, caplog):
        _fake_git(monkeypatch, stdout="a.py\n", returncode=128, stderr="bad ref")
        action = ChangeDetectionAction(project_dir=tmp_path)
        with caplog.at_level("WARNING"):
            assert action._get_changed_files() == []
        assert "bad ref" in caplog.text

    def test_subprocess_error_means_no_changes(self, tmp_path, monkeypatch):
        def boom(*args, **kwargs):
            raise FileNotFoundError("git")

        monkeypatch.setattr(cd.subprocess, "run", boom)
        action = ChangeDetectionAction(project_dir=tmp_path)
        assert action._get_changed_files() == []

    @pytest.mark.parametrize(
        ("base", "head", "offender"),
        [("--output=x", "HEAD", "base_ref"), ("HEAD~1", "-p", "head_ref")],
    )
    def test_option_like_refs_are_rejected_before_git_runs(
        self, tmp_path, monkeypatch, base, head, offender
    ):
        calls = _fake_git(monkeypatch, stdout="a.py\n")
        action = ChangeDetectionAction(
            project_dir=tmp_path, base_ref=base, head_ref=head
        )
        with pytest.raises(ValueError, match=offender):
            action._get_changed_files()
        assert calls == []

    def test_against_a_real_repository(self, tmp_path):
        def git(*args: str) -> None:
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=t",
                    "-c",
                    "user.email=t@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    *args,
                ],
                cwd=tmp_path,
                check=True,
                capture_output=True,
            )

        git("init", "-q", "-b", "main")
        _write(tmp_path, "a.py", "x = 1\n")
        git("add", "a.py")
        git("commit", "-q", "-m", "base")
        git("checkout", "-q", "-b", "feat")
        _write(tmp_path, "b.py", "y = 2\n")
        _write(tmp_path, "docs/c.md", "c\n")
        git("add", "b.py", "docs/c.md")
        git("commit", "-q", "-m", "feature")
        git("checkout", "-q", "main")
        _write(tmp_path, "later.py", "z = 3\n")
        git("add", "later.py")
        git("commit", "-q", "-m", "main moves on")

        action = ChangeDetectionAction(
            project_dir=tmp_path, base_ref="main", head_ref="feat"
        )
        # Three-dot diff: only what the feature branch added, not main's later work.
        assert action._get_changed_files() == ["b.py", "docs/c.md"]


# --------------------------------------------------------------------------
# ChangeDetectionAction.execute end to end
# --------------------------------------------------------------------------


def _run(tmp_path, monkeypatch, changed, **kwargs):
    _fake_git(monkeypatch, stdout="\n".join(changed) + "\n" if changed else "")
    action = ChangeDetectionAction(
        project_dir=tmp_path, reports_dir=tmp_path / "reports", **kwargs
    )
    return action, action.execute()


class TestExecute:
    def test_no_changes(self, tmp_path, monkeypatch):
        action, result = _run(tmp_path, monkeypatch, [])
        assert result.success is True
        assert result.changed_files == []
        assert result.classifications == {}
        assert result.change_categories == ""
        assert result.skip_tests is False
        assert result.skip_security is False
        assert result.skip_docs is False
        assert result.skip_lint is False
        assert result.optimization_score == 0
        assert result.failure_reason is None
        assert result.reports_path == str(tmp_path / "reports")
        assert not (tmp_path / "reports" / "change-detection-report.json").exists()

    def test_git_failure_is_treated_as_no_changes(self, tmp_path, monkeypatch):
        _fake_git(monkeypatch, returncode=1, stderr="fatal")
        result = ChangeDetectionAction(project_dir=tmp_path).execute()
        assert result.success is True
        assert result.changed_files == []
        assert result.skip_tests is False

    def test_docs_only_change_skips_expensive_jobs(self, tmp_path, monkeypatch):
        _, result = _run(tmp_path, monkeypatch, ["README.md", "docs/a.md"])
        assert result.success is True
        assert result.changed_files == ["README.md", "docs/a.md"]
        assert result.change_categories == "docs"
        assert result.skip_tests is True
        assert result.skip_security is True
        assert result.skip_lint is True
        assert result.skip_docs is False
        assert result.optimization_score == 75
        assert result.time_savings == 330
        assert result.affected_tests == []
        assert result.dependency_impact == 0

    def test_source_change_runs_full_pipeline_and_writes_reports(
        self, tmp_path, monkeypatch
    ):
        _write(tmp_path, "src/app.py", "import os\n")
        _write(tmp_path, "src/util.py", "import src.app\n")
        _write(tmp_path, "tests/test_app.py", "import src.app\n")
        changed = ["src/app.py", "src/util.py", "tests/test_app.py", "README.md"]
        _, result = _run(tmp_path, monkeypatch, changed)

        assert result.success is True
        assert result.change_categories == "docs,tests,source"
        assert result.classifications["source"] == ["src/app.py", "src/util.py"]
        assert result.classifications["tests"] == ["tests/test_app.py"]
        assert result.affected_tests == ["tests/test_app.py"]
        assert result.dependency_impact == 2
        assert result.skip_tests is False
        assert result.skip_security is False
        assert result.skip_lint is False
        assert result.skip_docs is False
        assert result.optimization_score == 0
        assert result.time_savings == 0
        assert result.execution_time >= 0

        report = json.loads(
            (tmp_path / "reports" / "change-detection-report.json").read_text()
        )
        assert report["success"] is True
        assert report["changed_files"] == changed
        assert report["dependency_graph"]["src/util.py"]["imports"] == ["src.app"]
        assert report["dependency_graph"]["src/app.py"]["imported_by"] == [
            "src/util.py"
        ]
        assert report["optimization_reasoning"]["tests"].startswith("Source")
        assert report["change_analysis"]["has_source"] is True
        assert (tmp_path / "reports" / "change-detection-summary.md").is_file()
        assert (tmp_path / "reports" / "change-detection-detailed.md").is_file()

    def test_changed_test_files_are_selected(self, tmp_path, monkeypatch):
        _write(tmp_path, "src/app.py")
        _write(tmp_path, "tests/test_a.py")
        _write(tmp_path, "tests/test_b.py")
        _, result = _run(
            tmp_path, monkeypatch, ["src/app.py", "tests/test_a.py", "tests/test_b.py"]
        )
        assert sorted(result.affected_tests) == ["tests/test_a.py", "tests/test_b.py"]

    @pytest.mark.parametrize(
        ("level", "impact"), [("standard", 1), ("comprehensive", 1), ("quick", 0)]
    )
    def test_detection_level_controls_dependency_analysis(
        self, tmp_path, monkeypatch, level, impact
    ):
        _write(tmp_path, "src/app.py")
        _, result = _run(tmp_path, monkeypatch, ["src/app.py"], detection_level=level)
        assert result.dependency_impact == impact
        report = json.loads(
            (tmp_path / "reports" / "change-detection-report.json").read_text()
        )
        assert bool(report["dependency_graph"]) is bool(impact)

    def test_disabling_optimizations_is_honoured(self, tmp_path, monkeypatch):
        _, result = _run(
            tmp_path,
            monkeypatch,
            ["README.md"],
            enable_test_optimization=False,
            enable_job_skipping=False,
        )
        assert result.skip_tests is False
        assert result.skip_security is False
        assert result.skip_lint is False
        assert result.skip_docs is False
        assert result.optimization_score == 0

    def test_monorepo_mode_reports_affected_packages(self, tmp_path, monkeypatch):
        _write(tmp_path, "libA/__init__.py")
        _write(tmp_path, "libA/mod.py")
        _write(tmp_path, "libB/pyproject.toml", '[project]\ndependencies = ["libA"]\n')
        _, result = _run(tmp_path, monkeypatch, ["libA/mod.py"], monorepo_mode=True)
        assert sorted(result.affected_packages) == ["libA", "libB"]

    def test_packages_not_reported_outside_monorepo_mode(self, tmp_path, monkeypatch):
        _write(tmp_path, "libA/__init__.py")
        _write(tmp_path, "libA/mod.py")
        _, result = _run(tmp_path, monkeypatch, ["libA/mod.py"])
        assert result.affected_packages == []

    def test_custom_patterns_change_classification(self, tmp_path, monkeypatch):
        _write(
            tmp_path,
            "patterns.json",
            json.dumps({"patterns": {"docs": ["manual/**"]}}),
        )
        _, result = _run(
            tmp_path,
            monkeypatch,
            ["manual/page.html"],
            pattern_config="patterns.json",
        )
        assert result.classifications["docs"] == ["manual/page.html"]
        assert result.skip_tests is True

    def test_unexpected_error_becomes_failed_result(self, tmp_path, monkeypatch):
        _fake_git(monkeypatch, stdout="a.py\n")
        action = ChangeDetectionAction(
            project_dir=tmp_path, reports_dir=tmp_path / "reports"
        )

        def boom(files):
            raise RuntimeError("classifier exploded")

        monkeypatch.setattr(action.pattern_matcher, "classify_files", boom)
        result = action.execute()
        assert result.success is False
        assert result.failure_reason == "classifier exploded"
        assert result.changed_files == []
        assert result.skip_tests is False
        assert result.reports_path == str(tmp_path / "reports")

    @pytest.mark.parametrize(
        ("base", "head", "offender"),
        [("-x", "HEAD", "base_ref"), ("HEAD~1", "--foo", "head_ref")],
    )
    def test_option_like_ref_fails_loudly_instead_of_no_changes(
        self, tmp_path, monkeypatch, base, head, offender
    ):
        calls = _fake_git(monkeypatch, stdout="a.py\n")
        action = ChangeDetectionAction(
            project_dir=tmp_path, base_ref=base, head_ref=head
        )
        result = action.execute()
        assert result.success is False
        assert offender in result.failure_reason
        assert calls == []
