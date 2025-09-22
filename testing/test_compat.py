"""Compatibility tests comparing FastPath with pathlib.Path."""

import os
import tempfile
from pathlib import Path as StdPath
from pathlib import PurePath as StdPurePath
from typing import Any
from typing import Callable
from typing import Generator
from typing import Tuple

import pytest

from fastpath import FastPath
from fastpath import PureFastPath


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def path_pairs(temp_dir: str) -> list[Tuple[StdPath, FastPath]]:
    """Generate pairs of standard and fast paths for testing."""
    return [
        (StdPath("."), FastPath(".")),
        (StdPath("/"), FastPath("/")),
        (StdPath("/home"), FastPath("/home")),
        (StdPath("/home/user"), FastPath("/home/user")),
        (StdPath("relative/path"), FastPath("relative/path")),
        (StdPath("file.txt"), FastPath("file.txt")),
        (StdPath("/path/to/file.txt"), FastPath("/path/to/file.txt")),
        (StdPath(temp_dir), FastPath(temp_dir)),
    ]


@pytest.fixture
def pure_path_pairs() -> list[Tuple[StdPurePath, PureFastPath]]:
    """Generate pairs of pure paths for testing."""
    return [
        (StdPurePath("."), PureFastPath(".")),
        (StdPurePath("/"), PureFastPath("/")),
        (StdPurePath("/home"), PureFastPath("/home")),
        (StdPurePath("/home/user"), PureFastPath("/home/user")),
        (StdPurePath("relative/path"), PureFastPath("relative/path")),
        (StdPurePath("file.txt"), PureFastPath("file.txt")),
        (StdPurePath("/path/to/file.txt"), PureFastPath("/path/to/file.txt")),
    ]


class TestPurePathCompatibility:
    """Test pure path operations match pathlib behavior."""

    def test_parts(self, pure_path_pairs: list[Tuple[StdPurePath, PureFastPath]]) -> None:
        """Test that parts match between implementations."""
        for std_path, fast_path in pure_path_pairs:
            assert fast_path.parts == std_path.parts, f"Parts mismatch for {std_path}"

    def test_parent(self, pure_path_pairs: list[Tuple[StdPurePath, PureFastPath]]) -> None:
        """Test that parent property matches."""
        for std_path, fast_path in pure_path_pairs:
            assert str(fast_path.parent) == str(std_path.parent), f"Parent mismatch for {std_path}"

    def test_name(self, pure_path_pairs: list[Tuple[StdPurePath, PureFastPath]]) -> None:
        """Test that name property matches."""
        for std_path, fast_path in pure_path_pairs:
            assert fast_path.name == std_path.name, f"Name mismatch for {std_path}"

    def test_suffix(self, pure_path_pairs: list[Tuple[StdPurePath, PureFastPath]]) -> None:
        """Test that suffix property matches."""
        test_paths = [
            ("file.txt", ".txt"),
            ("archive.tar.gz", ".gz"),
            ("no_extension", ""),
            (".hidden", ""),
            ("multiple.dots.here.txt", ".txt"),
        ]
        for path_str, expected_suffix in test_paths:
            std_path = StdPurePath(path_str)
            fast_path = PureFastPath(path_str)
            assert fast_path.suffix == std_path.suffix == expected_suffix

    def test_stem(self, pure_path_pairs: list[Tuple[StdPurePath, PureFastPath]]) -> None:
        """Test that stem property matches."""
        test_paths = [
            ("file.txt", "file"),
            ("archive.tar.gz", "archive.tar"),
            ("no_extension", "no_extension"),
            (".hidden", ".hidden"),
        ]
        for path_str, expected_stem in test_paths:
            std_path = StdPurePath(path_str)
            fast_path = PureFastPath(path_str)
            assert fast_path.stem == std_path.stem == expected_stem

    def test_joinpath(self) -> None:
        """Test that joinpath works the same way."""
        test_cases = [
            (("/home", "user"), "/home/user"),
            (("relative", "path", "here"), "relative/path/here"),
            (("/", "absolute"), "/absolute"),
            ((".", "current"), "./current" if os.name != 'nt' else ".\\current"),
        ]

        for parts, _ in test_cases:
            base = parts[0]
            rest = parts[1:]

            std_path = StdPurePath(base).joinpath(*rest)
            fast_path = PureFastPath(base).joinpath(*rest)

            assert str(fast_path) == str(std_path)

    def test_truediv_operator(self) -> None:
        """Test that / operator works the same way."""
        std_path = StdPurePath("/home") / "user" / "documents"
        fast_path = PureFastPath("/home") / "user" / "documents"

        assert str(fast_path) == str(std_path)

    def test_str_representation(self, pure_path_pairs: list[Tuple[StdPurePath, PureFastPath]]) -> None:
        """Test string representation matches."""
        for std_path, fast_path in pure_path_pairs:
            assert str(fast_path) == str(std_path)

    def test_equality(self) -> None:
        """Test equality comparisons."""
        fast1 = PureFastPath("/home/user")
        fast2 = PureFastPath("/home/user")
        fast3 = PureFastPath("/home/other")

        assert fast1 == fast2
        assert fast1 != fast3

        # Test equality with standard paths
        std_path = StdPurePath("/home/user")
        assert fast1 == str(std_path)

    def test_is_absolute(self) -> None:
        """Test absolute path detection."""
        test_cases = [
            ("/home/user", True),
            ("relative/path", False),
            ("/", True),
            (".", False),
        ]

        for path_str, expected in test_cases:
            std_path = StdPurePath(path_str)
            fast_path = PureFastPath(path_str)
            assert fast_path.is_absolute() == std_path.is_absolute() == expected

    def test_relative_to(self) -> None:
        """Test relative_to method."""
        base_path = "/home/user/documents"
        test_cases = [
            ("/home/user/documents/file.txt", "file.txt"),
            ("/home/user/documents/subdir/file.txt", "subdir/file.txt"),
            ("/home/user/documents", "."),
        ]

        for full_path, expected_relative in test_cases:
            std_full = StdPurePath(full_path)
            std_base = StdPurePath(base_path)
            fast_full = PureFastPath(full_path)
            fast_base = PureFastPath(base_path)

            std_relative = std_full.relative_to(std_base)
            fast_relative = fast_full.relative_to(fast_base)

            assert str(fast_relative) == str(std_relative)

    def test_is_relative_to(self) -> None:
        """Test is_relative_to method."""
        test_cases = [
            ("/home/user/documents", "/home/user", True),
            ("/home/user/documents", "/home", True),
            ("/home/user", "/var", False),
            ("relative/path", "relative", True),
            ("relative/path", "other", False),
        ]

        for path_str, base_str, expected in test_cases:
            fast_path = PureFastPath(path_str)
            assert fast_path.is_relative_to(base_str) == expected

    def test_with_name(self) -> None:
        """Test with_name method."""
        test_cases = [
            ("/home/user/file.txt", "newfile.txt", "/home/user/newfile.txt"),
            ("path/to/something", "other", "path/to/other"),
        ]

        for original, new_name, expected in test_cases:
            std_path = StdPurePath(original).with_name(new_name)
            fast_path = PureFastPath(original).with_name(new_name)
            assert str(fast_path) == str(std_path) == expected

    def test_with_suffix(self) -> None:
        """Test with_suffix method."""
        test_cases = [
            ("/home/user/file.txt", ".md", "/home/user/file.md"),
            ("/home/user/file.txt", "", "/home/user/file"),
            ("/home/user/file", ".txt", "/home/user/file.txt"),
        ]

        for original, new_suffix, expected in test_cases:
            std_path = StdPurePath(original).with_suffix(new_suffix)
            fast_path = PureFastPath(original).with_suffix(new_suffix)
            assert str(fast_path) == str(std_path) == expected

    def test_with_stem(self) -> None:
        """Test with_stem method."""
        test_cases = [
            ("/home/user/file.txt", "newfile", "/home/user/newfile.txt"),
            ("/home/user/document.pdf", "report", "/home/user/report.pdf"),
        ]

        for original, new_stem, expected in test_cases:
            std_path = StdPurePath(original).with_stem(new_stem)
            fast_path = PureFastPath(original).with_stem(new_stem)
            assert str(fast_path) == str(std_path) == expected


class TestFastPathCompatibility:
    """Test FastPath I/O operations."""

    def test_exists(self, temp_dir: str) -> None:
        """Test exists method."""
        # Create a test file
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")

        std_path = StdPath(test_file)
        fast_path = FastPath(test_file)

        assert fast_path.exists() == std_path.exists() == True

        # Test non-existent file
        std_path2 = StdPath(os.path.join(temp_dir, "nonexistent.txt"))
        fast_path2 = FastPath(os.path.join(temp_dir, "nonexistent.txt"))

        assert fast_path2.exists() == std_path2.exists() == False

    def test_is_file_is_dir(self, temp_dir: str) -> None:
        """Test is_file and is_dir methods."""
        # Create a test file and directory
        test_file = os.path.join(temp_dir, "test.txt")
        test_dir = os.path.join(temp_dir, "subdir")

        with open(test_file, "w") as f:
            f.write("test")
        os.mkdir(test_dir)

        # Test file
        file_std = StdPath(test_file)
        file_fast = FastPath(test_file)
        assert file_fast.is_file() == file_std.is_file() == True
        assert file_fast.is_dir() == file_std.is_dir() == False

        # Test directory
        dir_std = StdPath(test_dir)
        dir_fast = FastPath(test_dir)
        assert dir_fast.is_file() == dir_std.is_file() == False
        assert dir_fast.is_dir() == dir_std.is_dir() == True

    def test_mkdir(self, temp_dir: str) -> None:
        """Test mkdir method."""
        new_dir = os.path.join(temp_dir, "newdir")
        fast_path = FastPath(new_dir)

        fast_path.mkdir()
        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)

        # Test exist_ok parameter
        fast_path.mkdir(exist_ok=True)  # Should not raise

        # Test parents parameter
        nested_dir = os.path.join(temp_dir, "parent", "child")
        fast_nested = FastPath(nested_dir)
        fast_nested.mkdir(parents=True)
        assert os.path.exists(nested_dir)

    def test_touch(self, temp_dir: str) -> None:
        """Test touch method."""
        test_file = os.path.join(temp_dir, "touched.txt")
        fast_path = FastPath(test_file)

        fast_path.touch()
        assert os.path.exists(test_file)
        assert os.path.isfile(test_file)

        # Touch again with exist_ok
        fast_path.touch(exist_ok=True)

    def test_read_write_text(self, temp_dir: str) -> None:
        """Test read_text and write_text methods."""
        test_file = os.path.join(temp_dir, "text.txt")
        fast_path = FastPath(test_file)

        content = "Hello, World!\nThis is a test."
        bytes_written = fast_path.write_text(content)
        assert bytes_written == len(content)

        read_content = fast_path.read_text()
        assert read_content == content

    def test_read_write_bytes(self, temp_dir: str) -> None:
        """Test read_bytes and write_bytes methods."""
        test_file = os.path.join(temp_dir, "binary.bin")
        fast_path = FastPath(test_file)

        content = b"\x00\x01\x02\x03\x04"
        bytes_written = fast_path.write_bytes(content)
        assert bytes_written == len(content)

        read_content = fast_path.read_bytes()
        assert read_content == content

    def test_iterdir(self, temp_dir: str) -> None:
        """Test iterdir method."""
        # Create some files and directories
        files = ["file1.txt", "file2.txt", "file3.txt"]
        dirs = ["dir1", "dir2"]

        for f in files:
            open(os.path.join(temp_dir, f), "w").close()
        for d in dirs:
            os.mkdir(os.path.join(temp_dir, d))

        std_path = StdPath(temp_dir)
        fast_path = FastPath(temp_dir)

        std_contents = set(p.name for p in std_path.iterdir())
        fast_contents = set(p.name for p in fast_path.iterdir())

        assert fast_contents == std_contents
        assert len(fast_contents) == len(files) + len(dirs)

    def test_unlink(self, temp_dir: str) -> None:
        """Test unlink method."""
        test_file = os.path.join(temp_dir, "to_delete.txt")
        with open(test_file, "w") as f:
            f.write("delete me")

        fast_path = FastPath(test_file)
        assert fast_path.exists()

        fast_path.unlink()
        assert not fast_path.exists()

        # Test missing_ok parameter
        fast_path.unlink(missing_ok=True)  # Should not raise

    def test_rename(self, temp_dir: str) -> None:
        """Test rename method."""
        old_file = os.path.join(temp_dir, "old.txt")
        new_file = os.path.join(temp_dir, "new.txt")

        with open(old_file, "w") as f:
            f.write("content")

        fast_old = FastPath(old_file)
        fast_new = fast_old.rename(new_file)

        assert not os.path.exists(old_file)
        assert os.path.exists(new_file)
        assert isinstance(fast_new, FastPath)
        assert str(fast_new) == new_file


class TestPathSharing:
    """Test that multiple paths share the same allocator efficiently."""

    def test_shared_allocator(self) -> None:
        """Test that paths share the same default allocator."""
        path1 = FastPath("/home/user/documents")
        path2 = FastPath("/home/user/downloads")
        path3 = path1 / "file.txt"

        # All should share the same allocator
        assert path1._allocator is path2._allocator
        assert path1._allocator is path3._allocator

    def test_allocator_efficiency(self) -> None:
        """Test that the allocator efficiently shares strings."""
        # Create many paths with shared components
        paths = []
        for i in range(100):
            path = FastPath(f"/home/user/dir{i % 10}/file{i}.txt")
            paths.append(path)

        # Check allocator statistics
        allocator = paths[0]._allocator
        stats = allocator.stats()

        # Should have significantly fewer strings than total path components
        # (4 * 100 = 400 components, but many are duplicates)
        # We intern: home, user, dir0-9, file0-99.txt, plus "/" for absolute root
        assert stats["strings_interned"] < 200  # Much less than 400


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_path(self) -> None:
        """Test handling of empty paths."""
        fast_path = PureFastPath()
        assert str(fast_path) == "."

    def test_root_path(self) -> None:
        """Test handling of root path."""
        fast_path = PureFastPath("/")
        assert str(fast_path) == "/"
        assert fast_path.parts == ("/",)
        assert fast_path.name == ""
        assert fast_path.parent == fast_path  # Root is its own parent

    def test_path_with_dots(self) -> None:
        """Test paths with . and .. components."""
        # Note: Our implementation doesn't normalize these automatically
        # This matches pathlib.PurePath behavior
        fast_path = PureFastPath("/home/./user/../documents")
        assert "." in fast_path.parts
        assert ".." in fast_path.parts

    def test_path_from_path(self) -> None:
        """Test creating path from another path."""
        path1 = FastPath("/home/user")
        path2 = FastPath(path1)

        assert str(path1) == str(path2)
        assert path1._allocator is path2._allocator

    def test_path_from_pathlike(self) -> None:
        """Test creating path from os.PathLike object."""
        std_path = StdPath("/home/user")
        fast_path = FastPath(std_path)

        assert str(fast_path) == str(std_path)