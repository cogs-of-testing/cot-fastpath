#!/usr/bin/env python3
"""Example demonstrating FastPath usage and benefits."""

from fastpath import FastPath


def main():
    print("FastPath Example\n" + "=" * 50)

    # Create paths - they automatically share the same allocator
    home = FastPath("/home/user")
    docs = home / "documents"
    downloads = home / "downloads"

    print(f"Home: {home}")
    print(f"Documents: {docs}")
    print(f"Downloads: {downloads}")
    print()

    # Path operations
    file_path = docs / "reports" / "2024" / "quarterly.pdf"
    print(f"Full path: {file_path}")
    print(f"Parent: {file_path.parent}")
    print(f"Name: {file_path.name}")
    print(f"Stem: {file_path.stem}")
    print(f"Suffix: {file_path.suffix}")
    print(f"Parts: {file_path.parts}")
    print(f"Is absolute: {file_path.is_absolute()}")
    print()

    # Demonstrate memory efficiency
    print("Memory Efficiency Demo:")
    paths = []
    for project in range(10):
        for module in range(5):
            for file_num in range(20):
                path = FastPath(f"/projects/project_{project}/src/module_{module}/file_{file_num}.py")
                paths.append(path)

    # Check allocator statistics
    allocator = paths[0]._allocator
    stats = allocator.stats()

    print(f"Created {len(paths)} paths")
    print(f"Unique strings interned: {stats['strings_interned']}")
    print(f"Tree nodes allocated: {stats['nodes_allocated']}")
    print(f"Cache entries: {stats['cache_entries']}")

    # Calculate memory savings
    total_components = len(paths) * 5  # Each path has ~5 components
    savings_ratio = total_components / stats['strings_interned']
    print(f"String deduplication ratio: {savings_ratio:.1f}x")
    print()

    # Windows path support
    print("Windows Path Support:")
    win_path = FastPath("C:/Users/Documents/file.txt")
    print(f"Windows path: {win_path}")
    print(f"Parts: {win_path.parts}")
    print(f"Is absolute: {win_path.is_absolute()}")


if __name__ == "__main__":
    main()