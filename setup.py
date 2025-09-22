"""Setup script with mypyc compilation support."""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from setuptools import setup, find_packages


def get_mypyc_config() -> Dict[str, Any]:
    """Configure mypyc compilation if available."""
    try:
        from mypyc.build import mypycify
    except ImportError:
        print("mypyc not available, falling back to pure Python")
        return {}

    # Only compile the allocator module for now
    py_files = ["src/fastpath/_allocator.py"]

    if not py_files:
        print("No files to compile with mypyc")
        return {}

    print(f"Compiling with mypyc: {py_files}")

    # Ensure build directory exists
    build_dir = Path("build")
    build_dir.mkdir(exist_ok=True)

    return {
        "ext_modules": mypycify(
            py_files,
            opt_level="3",
            multi_file=False,  # Use single file mode to avoid header issues
            verbose=True,
        ),
        "packages": find_packages(where="src"),
        "package_dir": {"": "src"},
    }


if __name__ == "__main__":
    setup(**get_mypyc_config())
