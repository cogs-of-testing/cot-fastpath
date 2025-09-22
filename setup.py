"""Setup script with C extension support."""

from setuptools import setup, find_packages, Extension


# Define the unified C extension module
fastpath_module = Extension(
    "fastpath",
    sources=[
        "src/fastpath/module.c",
        "src/fastpath/allocator.c",
        "src/fastpath/path.c",
    ],
    include_dirs=["src/fastpath"],
    extra_compile_args=["-O3", "-Wall"],
)


if __name__ == "__main__":
    setup(
        ext_modules=[fastpath_module],
        packages=[],  # No Python packages, everything is in C
        package_dir={},
    )
