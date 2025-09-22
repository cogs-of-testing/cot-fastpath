"""Benchmarks comparing FastPath with pathlib.Path."""

import gc
import sys
from pathlib import Path as StdPath
from typing import Any
from typing import Type
from typing import Union

import pytest

from fastpath import FastPath
from fastpath._allocator import PathAllocator


PathClass = Union[Type[StdPath], Type[FastPath]]


class TestCreationBenchmarks:
    """Benchmark path creation operations."""

    @pytest.mark.parametrize(
        "path_cls",
        [StdPath, FastPath],
        ids=["std", "fast"],
    )
    def test_create_single_path(self, benchmark: Any, path_cls: PathClass) -> None:
        """Benchmark creating a single path."""
        benchmark(path_cls, "/home/user/documents/file.txt")

    @pytest.mark.parametrize(
        "path_cls",
        [StdPath, FastPath],
        ids=["std", "fast"],
    )
    def test_create_many_paths(self, benchmark: Any, path_cls: PathClass) -> None:
        """Benchmark creating many paths."""

        def create_paths() -> list:
            paths = []
            for i in range(1000):
                path = path_cls(f"/home/user/dir{i % 10}/file{i}.txt")
                paths.append(path)
            return paths

        benchmark(create_paths)


class TestOperationBenchmarks:
    """Benchmark path operations."""

    @pytest.mark.parametrize(
        "path_cls",
        [StdPath, FastPath],
        ids=["std", "fast"],
    )
    def test_joinpath(self, benchmark: Any, path_cls: PathClass) -> None:
        """Benchmark joinpath for paths."""
        base = path_cls("/home/user")

        def join_paths():
            return base / "documents" / "projects" / "code" / "file.py"

        benchmark(join_paths)

    @pytest.mark.parametrize(
        "path_cls",
        [StdPath, FastPath],
        ids=["std", "fast"],
    )
    def test_parent_access(self, benchmark: Any, path_cls: PathClass) -> None:
        """Benchmark parent access for paths."""
        path = path_cls("/home/user/documents/projects/code/file.py")

        def access_parents() -> list:
            parents = []
            current = path
            while current != current.parent:
                current = current.parent
                parents.append(current)
            return parents

        benchmark(access_parents)

    @pytest.mark.parametrize(
        "path_cls",
        [StdPath, FastPath],
        ids=["std", "fast"],
    )
    def test_parts_access(self, benchmark: Any, path_cls: PathClass) -> None:
        """Benchmark parts access for paths."""
        paths = [
            path_cls(f"/home/user/dir{i}/subdir/file{i}.txt")
            for i in range(100)
        ]

        def access_parts() -> list[tuple[str, ...]]:
            return [p.parts for p in paths]

        benchmark(access_parts)


class TestMemoryBenchmarks:
    """Benchmark memory usage."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Memory measurement differs on Windows")
    @pytest.mark.parametrize(
        "path_cls",
        [StdPath, FastPath],
        ids=["std", "fast"],
    )
    def test_memory_usage(self, benchmark: Any, path_cls: PathClass) -> None:
        """Measure memory for many paths."""

        def create_and_measure() -> tuple[list, int]:
            gc.collect()
            import tracemalloc

            tracemalloc.start()
            paths = []
            for i in range(10000):
                path = path_cls(f"/home/user/projects/repo{i % 100}/src/module{i % 50}/file{i}.py")
                paths.append(path)

            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            return paths, peak

        benchmark(create_and_measure)


class TestAllocatorBenchmarks:
    """Benchmark the allocator directly."""

    def test_string_interning(self, benchmark: Any) -> None:
        """Benchmark string interning."""
        allocator = PathAllocator()

        def intern_strings() -> list[int]:
            ids = []
            for i in range(1000):
                # Mix of new and repeated strings
                string = f"component_{i % 100}"
                string_id = allocator.string_pool.intern(string)
                ids.append(string_id)
            return ids

        benchmark(intern_strings)

    def test_path_construction(self, benchmark: Any) -> None:
        """Benchmark path construction in allocator."""
        allocator = PathAllocator()

        def construct_paths() -> list[int]:
            indices = []
            for i in range(1000):
                idx = allocator.from_parts(
                    "home",
                    "user",
                    f"dir{i % 10}",
                    f"file{i}.txt"
                )
                indices.append(idx)
            return indices

        benchmark(construct_paths)

    def test_tree_traversal(self, benchmark: Any) -> None:
        """Benchmark tree traversal operations."""
        allocator = PathAllocator()

        # Build a tree
        indices = []
        for i in range(100):
            idx = allocator.from_parts(
                "root",
                f"level1_{i % 5}",
                f"level2_{i % 10}",
                f"level3_{i % 20}",
                f"file{i}.txt"
            )
            indices.append(idx)

        def traverse_tree() -> list[tuple[str, ...]]:
            parts_list = []
            for idx in indices:
                parts = allocator.get_parts(idx)
                parts_list.append(parts)
            return parts_list

        benchmark(traverse_tree)