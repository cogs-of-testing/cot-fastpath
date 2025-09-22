"""Setup script with C extension support."""

from setuptools import setup, find_packages, Extension


# Define C extension modules
allocator_c = Extension(
    "fastpath._allocator_c",
    sources=["src/fastpath/_allocator_c.c"],
    extra_compile_args=["-O3", "-Wall", "-Wextra"],
)

path_c = Extension(
    "fastpath._path_c",
    sources=["src/fastpath/_path_c.c"],
    extra_compile_args=["-O3", "-Wall", "-Wextra"],
)


if __name__ == "__main__":
    setup(
        ext_modules=[allocator_c, path_c],
        packages=find_packages(where="src"),
        package_dir={"": "src"},
    )
