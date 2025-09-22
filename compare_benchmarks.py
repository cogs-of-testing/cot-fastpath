#!/usr/bin/env python3
"""Compare benchmark results between FastPath and standard pathlib."""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional


def format_time(seconds: float) -> str:
    """Format time in a human-readable way."""
    if seconds < 1e-6:
        return f"{seconds * 1e9:.2f}ns"
    elif seconds < 1e-3:
        return f"{seconds * 1e6:.2f}μs"
    elif seconds < 1:
        return f"{seconds * 1e3:.2f}ms"
    else:
        return f"{seconds:.2f}s"


def format_memory(bytes_val: float) -> str:
    """Format memory in a human-readable way."""
    if bytes_val < 1024:
        return f"{bytes_val:.0f}B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f}KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f}MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.1f}GB"


def compare_benchmarks(json_file: Optional[Path] = None) -> None:
    """Compare benchmark results from pytest-benchmark JSON output."""

    # Find the latest benchmark file if not specified
    if json_file is None:
        benchmark_dir = Path(".benchmarks")
        if not benchmark_dir.exists():
            print("No .benchmarks directory found. Run benchmarks first:")
            print("  uv run pytest testing/test_performance.py --benchmark-only --benchmark-save=comparison")
            return

        # Find the most recent JSON file
        json_files = list(benchmark_dir.glob("**/*.json"))
        if not json_files:
            print("No benchmark files found. Run benchmarks first.")
            return

        json_file = max(json_files, key=lambda p: p.stat().st_mtime)
        print(f"Using benchmark file: {json_file}\n")

    # Load benchmark data
    with open(json_file) as f:
        data = json.load(f)

    # Group benchmarks by test name and implementation
    results: Dict[str, Dict[str, Any]] = {}

    for bench in data.get("benchmarks", []):
        # Extract test name and implementation from parametrized test
        full_name = bench["fullname"]

        # Parse out the base test name and parameter
        if "[std]" in full_name:
            base_name = full_name.split("[std]")[0].split("::")[-1]
            impl = "std"
        elif "[fast]" in full_name:
            base_name = full_name.split("[fast]")[0].split("::")[-1]
            impl = "fast"
        else:
            continue

        if base_name not in results:
            results[base_name] = {}

        results[base_name][impl] = {
            "mean": bench["stats"]["mean"],
            "min": bench["stats"]["min"],
            "max": bench["stats"]["max"],
            "stddev": bench["stats"]["stddev"],
            "rounds": bench["stats"]["rounds"],
            "iterations": bench["stats"]["iterations"],
        }

    # Print comparison table
    print("=" * 90)
    print("BENCHMARK COMPARISON: FastPath vs Standard pathlib")
    print("=" * 90)
    print(f"{'Test':<40} {'Std Path':>12} {'FastPath':>12} {'Speedup':>10} {'Status':<15}")
    print("-" * 90)

    # Track overall performance
    speedups = []

    # Sort tests for consistent output
    for test_name in sorted(results.keys()):
        if "std" not in results[test_name] or "fast" not in results[test_name]:
            continue

        std_result = results[test_name]["std"]
        fast_result = results[test_name]["fast"]

        std_time = std_result["mean"]
        fast_time = fast_result["mean"]

        # Calculate speedup
        speedup = std_time / fast_time if fast_time > 0 else 0
        speedups.append(speedup)

        # Determine status with emojis
        if speedup > 3.0:
            status = "🚀 MUCH FASTER"
        elif speedup > 2.0:
            status = "⚡ Very Fast"
        elif speedup > 1.2:
            status = "✓ Faster"
        elif speedup > 0.95:
            status = "≈ Similar"
        else:
            status = "🐌 Slower"
            speedup = 1 / speedup  # Show slowdown factor

        # Format display
        display_name = test_name
        if len(display_name) > 38:
            display_name = display_name[:35] + "..."

        print(f"{display_name:<40} {format_time(std_time):>12} {format_time(fast_time):>12} "
              f"{speedup:>9.2f}x {status:<15}")

    # Print summary statistics
    if speedups:
        print("-" * 90)
        avg_speedup = sum(speedups) / len(speedups)
        min_speedup = min(speedups)
        max_speedup = max(speedups)

        print(f"{'SUMMARY':.<40}")
        print(f"  Average speedup: {avg_speedup:.2f}x")
        print(f"  Best speedup:    {max_speedup:.2f}x")
        print(f"  Worst speedup:   {min_speedup:.2f}x")

        faster_count = sum(1 for s in speedups if s > 1.1)
        similar_count = sum(1 for s in speedups if 0.9 <= s <= 1.1)
        slower_count = sum(1 for s in speedups if s < 0.9)

        print(f"\n  Performance breakdown:")
        print(f"    Faster:  {faster_count}/{len(speedups)} tests")
        print(f"    Similar: {similar_count}/{len(speedups)} tests")
        print(f"    Slower:  {slower_count}/{len(speedups)} tests")

    print("=" * 90)
    print("\nLegend:")
    print("  🚀 = >3x faster  ⚡ = >2x faster  ✓ = >1.2x faster")
    print("  ≈ = within 5%    🐌 = slower")
    print("\nTip: Run with --benchmark-save=NAME to save results for later comparison")
    print("     Run with --benchmark-compare to compare multiple runs")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare FastPath vs standard pathlib benchmarks")
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to benchmark JSON file (default: use latest)",
    )

    args = parser.parse_args()
    compare_benchmarks(args.file)