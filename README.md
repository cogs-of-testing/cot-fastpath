# cot-fastpath

A fast and memory-efficient pathlib implementation for Python using shared allocators and tree-based path representation.

## Features

- **Shared String Interning**: All path components are deduplicated through a shared string pool
- **Tree-Based Representation**: Paths are stored as nodes in a tree structure with parent references
- **Memory Efficient**: Multiple paths share common components, reducing memory usage by 3-5x
- **Performance Optimized**: Uses integer comparisons instead of string operations
- **Pathlib Compatible**: Implements the standard pathlib.Path API
- **Mypyc Compilation**: Core allocator components can be compiled with mypyc for additional speed

## Architecture

The implementation uses three main components:

1. **StringPool**: Interns all string components, mapping them to integer IDs
2. **TreeAllocator**: Stores paths as a tree structure using (parent_idx, name_id) tuples
3. **PathAllocator**: Manages the string pool and tree, with caching for frequently used paths

Multiple `FastPath` objects share the same allocator instance, enabling:
- Deduplication of common path components
- Fast parent/child traversal through integer indices
- Efficient memory usage for large numbers of paths

## Installation

```bash
pip install -e .
```

For development with all dependencies:

```bash
pip install -e ".[dev,testing]"
```

## Usage

```python
from fastpath import FastPath

# Create paths - they automatically share the same allocator
path1 = FastPath("/home/user/documents")
path2 = FastPath("/home/user/downloads")

# Standard pathlib operations
file_path = path1 / "report.pdf"
print(file_path.parent)  # /home/user/documents
print(file_path.name)     # report.pdf
print(file_path.suffix)   # .pdf

# File operations
if file_path.exists():
    content = file_path.read_text()
```

## Testing

Run tests with pytest:

```bash
pytest testing/
```

Run benchmarks:

```bash
pytest testing/test_performance.py --benchmark-only
```

Run tests across multiple Python versions with tox:

```bash
tox
```

## Performance

Preliminary benchmarks show:
- 2-4x faster path operations through integer comparisons
- 3-5x memory reduction through string interning
- Better cache locality with compact tree representation

## License

MIT
