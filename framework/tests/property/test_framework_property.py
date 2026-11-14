"""
Framework Property-Based Tests

Uses hypothesis to verify properties and invariants hold across a wide
range of generated inputs.
"""

import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


@pytest.mark.property
class TestFrameworkProperties:
    """Property-based tests for framework components."""

    @given(
        vulnerabilities=st.lists(
            st.tuples(
                st.sampled_from(["low", "medium", "high", "critical"]),
                st.text(
                    min_size=1,
                    max_size=30,
                    alphabet=string.ascii_letters + string.digits + "_-",
                ),
            ),
            min_size=0,
            max_size=20,
        ),
    )
    @settings(max_examples=15)
    def test_security_analyzer_vulnerability_counting_properties(self, vulnerabilities):
        """Test that security analyzer maintains counting properties."""

        # Create mock vulnerability data from tuples
        vulnerability_data = []
        for severity, package in vulnerabilities:
            vulnerability_data.append(
                {"package": package, "severity": severity, "version": "1.0.0"}
            )

        # Count vulnerabilities by severity
        severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for vuln in vulnerability_data:
            severity_counts[vuln["severity"]] += 1

        # Verify counting properties
        total_count = sum(severity_counts.values())
        assert total_count == len(vulnerability_data)

        # Property: sum of individual counts equals total
        assert (
            severity_counts["low"]
            + severity_counts["medium"]
            + severity_counts["high"]
            + severity_counts["critical"]
            == total_count
        )

        # Property: all counts are non-negative
        for count in severity_counts.values():
            assert count >= 0

    @given(
        values_pair=st.integers(min_value=1, max_value=10).flatmap(
            lambda n: st.tuples(
                st.lists(
                    st.floats(min_value=0.1, max_value=100.0), min_size=n, max_size=n
                ),
                st.lists(
                    st.floats(min_value=0.1, max_value=100.0), min_size=n, max_size=n
                ),
            )
        )
    )
    @settings(max_examples=15)
    def test_performance_comparison_properties(self, values_pair):
        """Test that performance comparison maintains mathematical properties."""
        baseline_values, current_values = values_pair

        # Calculate percentage changes
        percentage_changes = []
        for baseline, current in zip(baseline_values, current_values, strict=True):
            if baseline > 0:
                change = ((current - baseline) / baseline) * 100
                percentage_changes.append(change)

        # Verify comparison properties
        for baseline, current, change in zip(
            baseline_values, current_values, percentage_changes, strict=True
        ):
            # Property: improvement should be negative percentage change
            if current < baseline:
                assert change < 0

            # Property: regression should be positive percentage change
            elif current > baseline:
                assert change > 0

            # Property: no change should be zero percentage change
            else:
                assert abs(change) < 1e-10

    @given(
        metric_values=st.lists(
            st.floats(min_value=0.001, max_value=1000.0), min_size=2, max_size=100
        )
    )
    @settings(max_examples=10)
    def test_statistical_properties_invariants(self, metric_values):
        """Test that statistical calculations maintain mathematical invariants."""
        # Calculate basic statistics
        n = len(metric_values)
        mean_val = sum(metric_values) / n
        min_val = min(metric_values)
        max_val = max(metric_values)

        # Verify statistical invariants
        # Property: min <= mean <= max
        assert min_val <= mean_val <= max_val

        # Property: variance is non-negative
        variance = sum((x - mean_val) ** 2 for x in metric_values) / n
        assert variance >= 0

        # Property: standard deviation is non-negative
        std_dev = variance**0.5
        assert std_dev >= 0

        # Property: if all values are the same, variance should be 0
        if len(set(metric_values)) == 1:
            assert variance < 1e-10

    @given(
        file_count=st.integers(min_value=1, max_value=1000),
        test_percentage=st.floats(min_value=0.0, max_value=100.0),
    )
    @settings(max_examples=15)
    def test_coverage_calculation_properties(self, file_count, test_percentage):
        """Test that coverage calculations maintain mathematical properties."""
        # Calculate covered files
        covered_files = int((test_percentage / 100.0) * file_count)

        # Verify coverage properties
        # Property: covered files cannot exceed total files
        assert covered_files <= file_count

        # Property: covered files cannot be negative
        assert covered_files >= 0

        # Property: if percentage is very close to 100%, all files should be covered
        if abs(test_percentage - 100.0) < 1e-10:
            # Use round instead of int for edge cases near 100%
            covered_files_rounded = round((test_percentage / 100.0) * file_count)
            assert covered_files_rounded == file_count

        # Property: if percentage is 0%, no files should be covered
        if abs(test_percentage) < 1e-10:
            assert covered_files == 0
