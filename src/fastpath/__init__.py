"""Fast and memory-efficient pathlib implementation."""

# Import C implementation
from fastpath._path_c import FastPath
from fastpath._path_c import PureFastPath


__version__ = "0.1.0"
__all__ = ["FastPath", "PureFastPath"]