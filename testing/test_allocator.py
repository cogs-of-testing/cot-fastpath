"""Tests for the allocator module."""

import pytest

from fastpath._allocator_c import PathAllocator
from fastpath._allocator_c import StringPool
from fastpath._allocator_c import TreeAllocator
from fastpath._allocator_c import ROOT_PARENT


class TestStringPool:
    """Test the string interning pool."""

    def test_intern_new_string(self) -> None:
        """Test interning a new string."""
        pool = StringPool()
        id1 = pool.intern("hello")
        assert id1 == 0
        assert pool.get_string(id1) == "hello"

    def test_intern_duplicate_string(self) -> None:
        """Test interning returns same ID for duplicate."""
        pool = StringPool()
        id1 = pool.intern("hello")
        id2 = pool.intern("hello")
        assert id1 == id2

    def test_intern_multiple_strings(self) -> None:
        """Test interning multiple different strings."""
        pool = StringPool()
        id1 = pool.intern("hello")
        id2 = pool.intern("world")
        id3 = pool.intern("test")

        assert id1 == 0
        assert id2 == 1
        assert id3 == 2

        assert pool.get_string(id1) == "hello"
        assert pool.get_string(id2) == "world"
        assert pool.get_string(id3) == "test"

    def test_len(self) -> None:
        """Test string pool length."""
        pool = StringPool()
        assert len(pool) == 0

        pool.intern("a")
        assert len(pool) == 1

        pool.intern("b")
        assert len(pool) == 2

        pool.intern("a")  # Duplicate
        assert len(pool) == 2


class TestTreeAllocator:
    """Test the tree allocator."""

    def test_root_nodes(self) -> None:
        """Test root node creation."""
        pool = StringPool()
        tree = TreeAllocator(pool)

        # Test relative root
        assert tree.relative_root == 0
        assert tree.get_parent_idx(tree.relative_root) == ROOT_PARENT
        assert pool.get_string(tree.get_name_id(tree.relative_root)) == ""

        # Test absolute root
        assert tree.absolute_root == 1
        assert tree.get_parent_idx(tree.absolute_root) == ROOT_PARENT
        assert pool.get_string(tree.get_name_id(tree.absolute_root)) == "/"

    def test_add_node(self) -> None:
        """Test adding nodes to the tree."""
        pool = StringPool()
        tree = TreeAllocator(pool)

        name_id = pool.intern("child")
        child_idx = tree.add_node(tree.relative_root, name_id)

        assert child_idx >= 2  # After relative and absolute roots
        assert tree.get_parent_idx(child_idx) == tree.relative_root
        assert tree.get_name_id(child_idx) == name_id

    def test_get_parts(self) -> None:
        """Test getting path parts."""
        pool = StringPool()
        tree = TreeAllocator(pool)

        # Create path home/user/documents (relative)
        home_id = pool.intern("home")
        user_id = pool.intern("user")
        docs_id = pool.intern("documents")

        home_idx = tree.add_node(tree.relative_root, home_id)
        user_idx = tree.add_node(home_idx, user_id)
        docs_idx = tree.add_node(user_idx, docs_id)

        parts = tree.get_parts(docs_idx)
        assert parts == ["home", "user", "documents"]

    def test_find_child(self) -> None:
        """Test finding child nodes."""
        pool = StringPool()
        tree = TreeAllocator(pool)

        name_id1 = pool.intern("child1")
        name_id2 = pool.intern("child2")

        child1_idx = tree.add_node(tree.relative_root, name_id1)
        child2_idx = tree.add_node(tree.relative_root, name_id2)

        assert tree.find_child(tree.relative_root, name_id1) == child1_idx
        assert tree.find_child(tree.relative_root, name_id2) == child2_idx
        assert tree.find_child(tree.relative_root, pool.intern("nonexistent")) is None


class TestPathAllocator:
    """Test the path allocator."""

    def test_from_parts_empty(self) -> None:
        """Test creating empty path."""
        allocator = PathAllocator()
        idx = allocator.from_parts()
        assert idx == allocator.tree.relative_root
        assert allocator.get_parts(idx) == ()

    def test_from_parts_single(self) -> None:
        """Test creating single-part path."""
        allocator = PathAllocator()
        idx = allocator.from_parts("home")
        assert allocator.get_parts(idx) == ("home",)

    def test_from_parts_multiple(self) -> None:
        """Test creating multi-part path."""
        allocator = PathAllocator()
        idx = allocator.from_parts("home", "user", "documents")
        assert allocator.get_parts(idx) == ("home", "user", "documents")

    def test_from_parts_with_separator(self) -> None:
        """Test creating path with separators in parts."""
        allocator = PathAllocator()
        idx = allocator.from_parts("home/user", "documents")
        assert allocator.get_parts(idx) == ("home", "user", "documents")

    def test_from_string(self) -> None:
        """Test creating path from string."""
        allocator = PathAllocator()

        idx1 = allocator.from_string("/home/user/documents")
        assert allocator.get_parts(idx1) == ("home", "user", "documents")
        assert allocator.is_absolute(idx1) == True

        idx2 = allocator.from_string("relative/path")
        assert allocator.get_parts(idx2) == ("relative", "path")
        assert allocator.is_absolute(idx2) == False

        idx3 = allocator.from_string("/")
        assert idx3 == allocator.tree.absolute_root
        assert allocator.is_absolute(idx3) == True

    def test_caching(self) -> None:
        """Test that identical paths share the same index."""
        allocator = PathAllocator()

        idx1 = allocator.from_parts("home", "user")
        idx2 = allocator.from_parts("home", "user")
        assert idx1 == idx2

        # Verify cache is working
        assert len(allocator._cache) > 0

    def test_get_parent(self) -> None:
        """Test getting parent index."""
        allocator = PathAllocator()

        idx = allocator.from_parts("home", "user", "documents")
        parent_idx = allocator.get_parent(idx)

        assert parent_idx is not None
        assert allocator.get_parts(parent_idx) == ("home", "user")

        # Test root has no parent
        root_parent = allocator.get_parent(allocator.tree.relative_root)
        assert root_parent is None

    def test_get_name(self) -> None:
        """Test getting name of path."""
        allocator = PathAllocator()

        idx = allocator.from_parts("home", "user", "document.txt")
        assert allocator.get_name(idx) == "document.txt"

        # Test root names
        assert allocator.get_name(allocator.tree.relative_root) == ""
        assert allocator.get_name(allocator.tree.absolute_root) == ""

    def test_join(self) -> None:
        """Test joining path parts."""
        allocator = PathAllocator()

        base_idx = allocator.from_parts("home", "user")
        new_idx = allocator.join(base_idx, "documents", "file.txt")

        assert allocator.get_parts(new_idx) == ("home", "user", "documents", "file.txt")

    def test_stats(self) -> None:
        """Test allocator statistics."""
        allocator = PathAllocator()

        # Create some paths
        allocator.from_parts("home", "user")
        allocator.from_parts("var", "log")
        allocator.from_parts("home", "user", "documents")

        stats = allocator.stats()
        assert "strings_interned" in stats
        assert "nodes_allocated" in stats
        assert "cache_entries" in stats
        assert stats["strings_interned"] > 0
        assert stats["nodes_allocated"] > 0
        assert stats["cache_entries"] > 0


class TestAllocatorIntegration:
    """Integration tests for the allocator system."""

    def test_large_tree(self) -> None:
        """Test handling a large tree structure."""
        allocator = PathAllocator()

        # Create many paths with shared components
        paths = []
        for i in range(10):
            for j in range(10):
                idx = allocator.from_parts("root", f"dir{i}", f"subdir{j}", "file.txt")
                paths.append(idx)

        # Verify deduplication worked
        stats = allocator.stats()
        # Should have much fewer strings than total path components
        assert stats["strings_interned"] < 200  # ~23 unique strings

    def test_path_sharing(self) -> None:
        """Test that shared path prefixes share nodes."""
        allocator = PathAllocator()

        idx1 = allocator.from_parts("home", "user", "docs", "file1.txt")
        idx2 = allocator.from_parts("home", "user", "docs", "file2.txt")
        idx3 = allocator.from_parts("home", "user", "downloads")

        # Get parent indices
        parent1 = allocator.get_parent(idx1)
        parent2 = allocator.get_parent(idx2)

        # file1.txt and file2.txt should share the same parent
        assert parent1 == parent2

        # All three should share home/user prefix
        assert allocator.get_parent(parent1) == allocator.get_parent(idx3)