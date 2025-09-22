"""Pytest configuration and custom benchmark comparison."""

import pytest
from typing import Dict, Any, List


def pytest_sessionfinish(session, exitstatus):
    """Print benchmark comparison summary after all tests."""
    if not hasattr(session, "_benchmark_results"):
        return

    results = session._benchmark_results
    if not results:
        return

    # Group results by test name (without [std] or [fast] suffix)
    comparisons = {}
    for name, stats in results.items():
        if "[std]" in name:
            base_name = name.replace("[std]", "")
            impl = "std"
        elif "[fast]" in name:
            base_name = name.replace("[fast]", "")
            impl = "fast"
        else:
            continue

        if base_name not in comparisons:
            comparisons[base_name] = {}
        comparisons[base_name][impl] = stats

    # Print comparison table
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON: FastPath vs Standard pathlib")
    print("=" * 80)
    print(f"{'Test':<50} {'Speedup':>10} {'Status':>10}")
    print("-" * 80)

    total_speedup = []

    for test_name in sorted(comparisons.keys()):
        if "std" not in comparisons[test_name] or "fast" not in comparisons[test_name]:
            continue

        std_time = comparisons[test_name]["std"]["mean"]
        fast_time = comparisons[test_name]["fast"]["mean"]

        if fast_time > 0:
            speedup = std_time / fast_time
            total_speedup.append(speedup)

            if speedup > 2.0:
                status = "🚀 FASTER"
                speedup_str = f"{speedup:.2f}x"
            elif speedup > 1.1:
                status = "✓ faster"
                speedup_str = f"{speedup:.2f}x"
            elif speedup > 0.9:
                status = "≈ same"
                speedup_str = f"{speedup:.2f}x"
            else:
                status = "⚠ slower"
                speedup_str = f"{1/speedup:.2f}x slower"
        else:
            status = "?"
            speedup_str = "N/A"

        # Shorten test name if needed
        display_name = test_name
        if len(display_name) > 48:
            display_name = display_name[:45] + "..."

        print(f"{display_name:<50} {speedup_str:>10} {status:>10}")

    if total_speedup:
        avg_speedup = sum(total_speedup) / len(total_speedup)
        print("-" * 80)
        print(f"{'Average speedup:':<50} {avg_speedup:>10.2f}x")

    print("=" * 80)
    print("Legend: 🚀 = >2x faster, ✓ = >1.1x faster, ≈ = similar (0.9-1.1x), ⚠ = slower")
    print("=" * 80 + "\n")


@pytest.fixture(autouse=True)
def capture_benchmark_results(request):
    """Capture benchmark results for comparison."""
    # Only proceed if benchmark fixture is actually used
    if "benchmark" not in request.fixturenames:
        yield
        return

    benchmark = request.getfixturevalue("benchmark")
    yield

    # Store results in session for later comparison
    if hasattr(benchmark, "stats"):
        if not hasattr(request.session, "_benchmark_results"):
            request.session._benchmark_results = {}
        request.session._benchmark_results[request.node.name] = benchmark.stats