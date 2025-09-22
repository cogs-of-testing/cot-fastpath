"""Fast path implementation compatible with pathlib.

Provides FastPath and PureFastPath classes that use the allocator
system for efficient memory usage and operations.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path as StdPath
from typing import TYPE_CHECKING
from typing import Any
from typing import Generator
from typing import Iterator
from typing import Optional
from typing import Union

from fastpath._allocator import PathAllocator


if TYPE_CHECKING:
    from os import PathLike


_default_allocator: Optional[PathAllocator] = None


def get_default_allocator() -> PathAllocator:
    """Get or create the default shared allocator."""
    global _default_allocator
    if _default_allocator is None:
        _default_allocator = PathAllocator(separator=os.sep)
    return _default_allocator


class PureFastPath:
    """Pure path operations without I/O.

    Provides path manipulation and inspection operations that don't
    require filesystem access.
    """

    __slots__ = ("_allocator", "_node_idx")

    def __init__(
        self,
        *parts: Union[str, "PathLike[str]", "PureFastPath"],
        allocator: Optional[PathAllocator] = None,
        _node_idx: Optional[int] = None,
    ) -> None:
        """Initialize a pure path from parts or a node index.

        Args:
            *parts: Path components or existing paths to join
            allocator: Optional allocator to use (defaults to shared)
            _node_idx: Internal node index (for internal use only)
        """
        self._allocator = allocator or get_default_allocator()

        if _node_idx is not None:
            # Direct node index provided (internal use)
            self._node_idx = _node_idx
        else:
            # Convert all parts to strings
            str_parts: list[str] = []
            for part in parts:
                if isinstance(part, PureFastPath):
                    # Reuse the parts from existing FastPath
                    str_parts.extend(part.parts)
                elif isinstance(part, str):
                    str_parts.append(part)
                elif hasattr(part, "__fspath__"):
                    str_parts.append(os.fspath(part))
                else:
                    str_parts.append(str(part))

            # Create the path in the allocator
            if str_parts:
                self._node_idx = self._allocator.from_parts(*str_parts)
            else:
                self._node_idx = self._allocator.tree.relative_root


    @property
    def parts(self) -> tuple[str, ...]:
        """Return the path components as a tuple."""
        parts = self._allocator.get_parts(self._node_idx)
        root_type = self._allocator.tree.get_root_type(self._node_idx)

        # Handle different root types
        if root_type == "absolute":
            # Absolute POSIX path - prepend separator
            if not parts:
                return (self._allocator._separator,)
            return (self._allocator._separator,) + parts
        elif root_type.startswith("drive:"):
            # Windows drive path
            drive = root_type.split(":")[1]
            if not parts:
                return (f"{drive}:",)
            return (f"{drive}:",) + parts
        else:
            # Relative path
            if not parts:
                # Empty relative path
                return ()
            return parts

    @property
    def parent(self) -> "PureFastPath":
        """Return the parent directory."""
        parent_idx = self._allocator.get_parent(self._node_idx)
        if parent_idx is None:
            # Already at root, return self
            return self
        return type(self)(allocator=self._allocator, _node_idx=parent_idx)

    @property
    def parents(self) -> tuple["PureFastPath", ...]:
        """Return all parent directories."""
        parents_list: list[PureFastPath] = []
        current = self.parent

        while current != current.parent:  # Stop when we reach root
            parents_list.append(current)
            current = current.parent

        # Add final root if we have parents
        if parents_list and self._allocator.tree.is_root(current._node_idx):
            parents_list.append(current)

        return tuple(parents_list)

    @property
    def name(self) -> str:
        """Return the final path component."""
        return self._allocator.get_name(self._node_idx)

    @property
    def suffix(self) -> str:
        """Return the file extension."""
        name = self.name
        if not name:
            return ""
        idx = name.rfind(".")
        if idx > 0:  # Don't count leading dots
            return name[idx:]
        return ""

    @property
    def suffixes(self) -> list[str]:
        """Return all file extensions."""
        name = self.name
        if not name:
            return []

        suffixes = []
        while True:
            idx = name.find(".")
            if idx < 0 or idx == len(name) - 1:
                break
            if idx > 0:  # Don't count leading dots
                name = name[idx:]
                suffixes.append(name[:name.find(".", 1)] if "." in name[1:] else name)
                name = name[1:]
            else:
                name = name[1:]
        return suffixes

    @property
    def stem(self) -> str:
        """Return the final path component without extension."""
        name = self.name
        if not name:
            return ""
        suffix = self.suffix
        if suffix:
            return name[:-len(suffix)]
        return name

    def joinpath(self, *other: Union[str, "PathLike[str]", "PureFastPath"]) -> "PureFastPath":
        """Join path components."""
        if not other:
            return self

        # Convert other parts to strings
        str_parts: list[str] = []
        for part in other:
            if isinstance(part, PureFastPath):
                str_parts.extend(part.parts)
            elif isinstance(part, str):
                str_parts.append(part)
            elif hasattr(part, "__fspath__"):
                str_parts.append(os.fspath(part))
            else:
                str_parts.append(str(part))

        new_idx = self._allocator.join(self._node_idx, *str_parts)
        return type(self)(allocator=self._allocator, _node_idx=new_idx)

    def __truediv__(self, other: Union[str, "PathLike[str]", "PureFastPath"]) -> "PureFastPath":
        """Join paths with / operator."""
        return self.joinpath(other)

    def __str__(self) -> str:
        """Return string representation of the path."""
        parts = self.parts
        if not parts:
            return "."

        # Handle absolute POSIX path
        if parts[0] == self._allocator._separator:
            if len(parts) == 1:
                return self._allocator._separator
            return self._allocator._separator + self._allocator._separator.join(parts[1:])

        # Handle Windows drive path
        if parts[0].endswith(":"):
            if len(parts) == 1:
                return parts[0]
            # Use appropriate separator for Windows paths
            sep = "\\" if os.name == "nt" else "/"
            return parts[0] + sep + sep.join(parts[1:])

        # Relative path
        return self._allocator._separator.join(parts)

    def __repr__(self) -> str:
        """Return representation for debugging."""
        return f"{self.__class__.__name__}({str(self)!r})"

    def __fspath__(self) -> str:
        """Return the path as a string for os.PathLike protocol."""
        return str(self)

    def __eq__(self, other: Any) -> bool:
        """Check equality with another path."""
        if not isinstance(other, (PureFastPath, StdPath, str)):
            return NotImplemented

        if isinstance(other, PureFastPath):
            # Fast path for same allocator
            if self._allocator is other._allocator:
                return self._node_idx == other._node_idx
            # Compare parts for different allocators
            return self.parts == other.parts

        # Compare string representations for other types
        return str(self) == str(other)

    def __hash__(self) -> int:
        """Return hash for use in sets and dicts."""
        return hash((self._allocator, self._node_idx))

    def as_posix(self) -> str:
        """Return the path with forward slashes."""
        parts = self.parts
        if not parts:
            return "."
        # Handle absolute paths
        if parts[0] == "/":
            if len(parts) == 1:
                return "/"
            return "/" + "/".join(parts[1:])
        # Handle Windows drive paths
        if parts[0].endswith(":"):
            if len(parts) == 1:
                return parts[0]
            return parts[0] + "/" + "/".join(parts[1:])
        # Relative paths
        return "/".join(parts)

    def is_absolute(self) -> bool:
        """Check if this is an absolute path."""
        return self._allocator.is_absolute(self._node_idx)

    def is_relative_to(self, other: Union[str, "PathLike[str]", "PureFastPath"]) -> bool:
        """Check if this path is relative to another."""
        if isinstance(other, str):
            other = PureFastPath(other, allocator=self._allocator)
        elif not isinstance(other, PureFastPath):
            other = PureFastPath(os.fspath(other), allocator=self._allocator)

        my_parts = self.parts
        other_parts = other.parts

        if len(other_parts) > len(my_parts):
            return False

        return my_parts[:len(other_parts)] == other_parts

    def relative_to(self, other: Union[str, "PathLike[str]", "PureFastPath"]) -> "PureFastPath":
        """Return a relative path to another path."""
        if not self.is_relative_to(other):
            raise ValueError(f"{self} is not relative to {other}")

        if isinstance(other, str):
            other = type(self)(other, allocator=self._allocator)
        elif not isinstance(other, type(self)):
            other = type(self)(os.fspath(other), allocator=self._allocator)

        my_parts = self.parts
        other_parts = other.parts

        relative_parts = my_parts[len(other_parts):]
        if relative_parts:
            return type(self)(*relative_parts, allocator=self._allocator)
        return type(self)(".", allocator=self._allocator)

    def with_name(self, name: str) -> "PureFastPath":
        """Return a path with the name replaced."""
        if not self.name:
            raise ValueError("Path has no name to replace")
        parent = self.parent
        return parent / name

    def with_suffix(self, suffix: str) -> "PureFastPath":
        """Return a path with the suffix replaced."""
        if not suffix:
            return self.with_name(self.stem)
        if not suffix.startswith("."):
            suffix = "." + suffix
        return self.with_name(self.stem + suffix)

    def with_stem(self, stem: str) -> "PureFastPath":
        """Return a path with the stem replaced."""
        return self.with_name(stem + self.suffix)


class FastPath(PureFastPath):
    """Fast path implementation with filesystem operations.

    Extends PureFastPath with I/O operations like exists(), is_file(), etc.
    """

    def __init__(
        self,
        *parts: Union[str, "PathLike[str]", "FastPath"],
        allocator: Optional[PathAllocator] = None,
        _node_idx: Optional[int] = None,
    ) -> None:
        """Initialize a path from parts or a node index."""
        super().__init__(*parts, allocator=allocator, _node_idx=_node_idx)

    @property
    def parent(self) -> "FastPath":
        """Return the parent directory."""
        parent_idx = self._allocator.get_parent(self._node_idx)
        if parent_idx is None:
            return self
        return type(self)(allocator=self._allocator, _node_idx=parent_idx)

    @property
    def parents(self) -> tuple["FastPath", ...]:
        """Return all parent directories."""
        parents_list: list[FastPath] = []
        current = self.parent

        while current != current.parent:
            parents_list.append(current)
            current = current.parent

        # Add final root if we have parents
        if parents_list and self._allocator.tree.is_root(current._node_idx):
            parents_list.append(current)

        return tuple(parents_list)

    def joinpath(self, *other: Union[str, "PathLike[str]", "FastPath"]) -> "FastPath":
        """Join path components."""
        result = super().joinpath(*other)
        return type(self)(allocator=self._allocator, _node_idx=result._node_idx)

    def __truediv__(self, other: Union[str, "PathLike[str]", "FastPath"]) -> "FastPath":
        """Join paths with / operator."""
        return self.joinpath(other)

    def exists(self) -> bool:
        """Check if the path exists."""
        return os.path.exists(str(self))

    def is_file(self) -> bool:
        """Check if this is a regular file."""
        return os.path.isfile(str(self))

    def is_dir(self) -> bool:
        """Check if this is a directory."""
        return os.path.isdir(str(self))

    def is_symlink(self) -> bool:
        """Check if this is a symbolic link."""
        return os.path.islink(str(self))

    def stat(self) -> os.stat_result:
        """Get file statistics."""
        return os.stat(str(self))

    def lstat(self) -> os.stat_result:
        """Get file statistics without following symlinks."""
        return os.lstat(str(self))

    def resolve(self, strict: bool = False) -> "FastPath":
        """Resolve symlinks and return absolute path."""
        resolved = os.path.realpath(str(self))
        return FastPath(resolved, allocator=self._allocator)

    def absolute(self) -> "FastPath":
        """Return absolute version of the path."""
        if self.is_absolute():
            return self
        abs_path = os.path.abspath(str(self))
        return FastPath(abs_path, allocator=self._allocator)

    def cwd(self) -> "FastPath":
        """Return the current working directory."""
        return FastPath(os.getcwd(), allocator=self._allocator)

    def home(self) -> "FastPath":
        """Return the home directory."""
        return FastPath(os.path.expanduser("~"), allocator=self._allocator)

    def iterdir(self) -> Generator["FastPath", None, None]:
        """Iterate over directory contents."""
        path_str = str(self)
        try:
            for name in os.listdir(path_str):
                yield self / name
        except OSError:
            return

    def glob(self, pattern: str) -> Generator["FastPath", None, None]:
        """Glob the given pattern in the directory."""
        import glob as glob_module

        path_str = str(self)
        full_pattern = os.path.join(path_str, pattern)

        for match in glob_module.glob(full_pattern):
            yield FastPath(match, allocator=self._allocator)

    def rglob(self, pattern: str) -> Generator["FastPath", None, None]:
        """Recursively glob the given pattern."""
        return self.glob(f"**/{pattern}")

    def mkdir(
        self,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        """Create directory."""
        path_str = str(self)
        if parents:
            os.makedirs(path_str, mode=mode, exist_ok=exist_ok)
        else:
            try:
                os.mkdir(path_str, mode=mode)
            except FileExistsError:
                if not exist_ok:
                    raise

    def rmdir(self) -> None:
        """Remove empty directory."""
        os.rmdir(str(self))

    def unlink(self, missing_ok: bool = False) -> None:
        """Remove file."""
        try:
            os.unlink(str(self))
        except FileNotFoundError:
            if not missing_ok:
                raise

    def rename(self, target: Union[str, "PathLike[str]", "FastPath"]) -> "FastPath":
        """Rename file or directory."""
        if isinstance(target, FastPath):
            target_str = str(target)
            result = target
        else:
            target_str = os.fspath(target) if hasattr(target, "__fspath__") else str(target)
            result = FastPath(target_str, allocator=self._allocator)

        os.rename(str(self), target_str)
        return result

    def replace(self, target: Union[str, "PathLike[str]", "FastPath"]) -> "FastPath":
        """Replace file or directory, overwriting if it exists."""
        if isinstance(target, FastPath):
            target_str = str(target)
            result = target
        else:
            target_str = os.fspath(target) if hasattr(target, "__fspath__") else str(target)
            result = FastPath(target_str, allocator=self._allocator)

        os.replace(str(self), target_str)
        return result

    def touch(self, mode: int = 0o666, exist_ok: bool = True) -> None:
        """Create file if it doesn't exist, update timestamp if it does."""
        path_str = str(self)
        flags = os.O_CREAT | os.O_WRONLY
        if not exist_ok:
            flags |= os.O_EXCL

        fd = os.open(path_str, flags, mode)
        os.close(fd)

    def read_bytes(self) -> bytes:
        """Read file contents as bytes."""
        with open(str(self), "rb") as f:
            return f.read()

    def write_bytes(self, data: bytes) -> int:
        """Write bytes to file."""
        with open(str(self), "wb") as f:
            return f.write(data)

    def read_text(self, encoding: Optional[str] = None, errors: Optional[str] = None) -> str:
        """Read file contents as text."""
        with open(str(self), "r", encoding=encoding, errors=errors) as f:
            return f.read()

    def write_text(
        self,
        data: str,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        newline: Optional[str] = None,
    ) -> int:
        """Write text to file."""
        with open(str(self), "w", encoding=encoding, errors=errors, newline=newline) as f:
            return f.write(data)

    def open(
        self,
        mode: str = "r",
        buffering: int = -1,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        newline: Optional[str] = None,
    ) -> Any:
        """Open the file."""
        return open(str(self), mode, buffering, encoding, errors, newline)

    def with_name(self, name: str) -> "FastPath":
        """Return a path with the name replaced."""
        result = super().with_name(name)
        return type(self)(allocator=self._allocator, _node_idx=result._node_idx)

    def with_suffix(self, suffix: str) -> "FastPath":
        """Return a path with the suffix replaced."""
        result = super().with_suffix(suffix)
        return type(self)(allocator=self._allocator, _node_idx=result._node_idx)

    def with_stem(self, stem: str) -> "FastPath":
        """Return a path with the stem replaced."""
        result = super().with_stem(stem)
        return type(self)(allocator=self._allocator, _node_idx=result._node_idx)
