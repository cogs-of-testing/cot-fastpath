"""Core allocator implementation with string interning and tree structure.

This module is compiled with mypyc for optional performance optimization.
"""

from __future__ import annotations

from typing import Dict
from typing import Final
from typing import List
from typing import Optional
from typing import Tuple


class StringPool:
    """String interning pool for efficient string storage and lookup.

    Maps strings to integer IDs to enable fast integer-based comparisons
    and reduce memory usage through deduplication.
    """

    # Removed __slots__ for mypyc compatibility

    def __init__(self) -> None:
        self.strings: List[str] = []
        self.string_map: Dict[str, int] = {}

    def intern(self, s: str) -> int:
        """Intern a string and return its ID.

        If the string is already interned, returns the existing ID.
        Otherwise, adds it to the pool and returns the new ID.
        """
        if s in self.string_map:
            return self.string_map[s]

        string_id = len(self.strings)
        self.strings.append(s)
        self.string_map[s] = string_id
        return string_id

    def get_string(self, string_id: int) -> str:
        """Get the string associated with an ID."""
        return self.strings[string_id]

    def __len__(self) -> int:
        """Return the number of interned strings."""
        return len(self.strings)


class TreeNode:
    """A node in the path tree."""

    # Removed __slots__ for mypyc compatibility

    def __init__(self, parent_idx: int, name_id: int) -> None:
        self.parent_idx = parent_idx
        self.name_id = name_id


class TreeAllocator:
    """Tree-based path representation using parent references.

    Each node stores a reference to its parent node and the ID of its name
    component. This allows efficient traversal and parent/child operations.
    """

    # Removed __slots__ for mypyc compatibility

    ROOT_PARENT: Final[int] = -1

    def __init__(self, string_pool: StringPool) -> None:
        self.string_pool: StringPool = string_pool
        self.nodes: List[TreeNode] = []

        # Create different root nodes for different path types
        # Relative paths root (e.g., "relative/path")
        self.relative_root: int = self.add_node(self.ROOT_PARENT, string_pool.intern(""))

        # Absolute POSIX paths root (e.g., "/absolute/path")
        self.absolute_root: int = self.add_node(self.ROOT_PARENT, string_pool.intern("/"))

        # Windows drive roots (e.g., "C:", "D:")
        self.drive_roots: Dict[str, int] = {}

    def add_node(self, parent_idx: int, name_id: int) -> int:
        """Add a new node to the tree and return its index."""
        node_idx = len(self.nodes)
        self.nodes.append(TreeNode(parent_idx, name_id))
        return node_idx

    def get_or_create_drive_root(self, drive: str) -> int:
        """Get or create a root node for a Windows drive."""
        drive_upper = drive.upper()
        if drive_upper not in self.drive_roots:
            drive_id = self.string_pool.intern(drive_upper + ":")
            self.drive_roots[drive_upper] = self.add_node(self.ROOT_PARENT, drive_id)
        return self.drive_roots[drive_upper]

    def get_parent_idx(self, node_idx: int) -> int:
        """Get the parent index of a node."""
        return self.nodes[node_idx].parent_idx

    def get_name_id(self, node_idx: int) -> int:
        """Get the name ID of a node."""
        return self.nodes[node_idx].name_id

    def is_root(self, node_idx: int) -> bool:
        """Check if this node is a root node."""
        return self.nodes[node_idx].parent_idx == self.ROOT_PARENT

    def get_root_type(self, node_idx: int) -> str:
        """Determine the root type of a path."""
        # Walk up to find the root
        current_idx = node_idx
        while not self.is_root(current_idx):
            current_idx = self.get_parent_idx(current_idx)

        if current_idx == self.relative_root:
            return "relative"
        elif current_idx == self.absolute_root:
            return "absolute"
        else:
            # Check if it's a drive root
            for drive, root_idx in self.drive_roots.items():
                if current_idx == root_idx:
                    return f"drive:{drive}"
            return "unknown"

    def get_parts(self, node_idx: int) -> List[str]:
        """Get all path components from root to this node."""
        # Find the root
        current_idx = node_idx
        parts: List[str] = []

        while not self.is_root(current_idx):
            name_id = self.get_name_id(current_idx)
            name = self.string_pool.get_string(name_id)
            if name:  # Skip empty names
                parts.append(name)
            current_idx = self.get_parent_idx(current_idx)

        parts.reverse()
        return parts

    def find_child(self, parent_idx: int, name_id: int) -> Optional[int]:
        """Find a child node with the given name under the parent.

        This is a linear search for now; could be optimized with an index.
        """
        for idx, node in enumerate(self.nodes):
            if node.parent_idx == parent_idx and node.name_id == name_id:
                return idx
        return None


class PathAllocator:
    """Central allocator managing all path data.

    Combines string interning and tree structure with caching for
    efficient path operations and memory usage.
    """

    # Removed __slots__ for mypyc compatibility

    def __init__(self, separator: str = "/") -> None:
        self.string_pool = StringPool()
        self.tree = TreeAllocator(self.string_pool)
        self._cache: Dict[Tuple[str, ...], int] = {}
        self._separator = separator

    def _parse_path(self, path: str) -> Tuple[str, List[str]]:
        """Parse a path string to determine its type and components.

        Returns: (path_type, components)
        where path_type is one of: 'absolute', 'relative', 'drive:X'
        """
        if not path or path == ".":
            return ("relative", [])

        # Check for Windows drive letter (e.g., "C:", "C:/", "C:\\")
        if len(path) >= 2 and path[1] == ':':
            drive = path[0].upper()
            remainder = path[2:].lstrip("/\\")
            if remainder:
                parts = remainder.replace("\\", "/").split("/")
                return (f"drive:{drive}", [p for p in parts if p])
            else:
                return (f"drive:{drive}", [])

        # Check for absolute POSIX path
        if path.startswith("/"):
            parts = path[1:].split("/")
            return ("absolute", [p for p in parts if p])

        # Relative path
        parts = path.replace("\\", "/").split("/")
        return ("relative", [p for p in parts if p])

    def from_parts(self, *parts: str) -> int:
        """Create or retrieve a path from its components.

        Returns the node index for the path constructed from the given parts.
        Uses caching to avoid recreating existing paths.
        """
        if not parts:
            return self.tree.relative_root

        # Parse the first part to determine path type
        first_part = parts[0]
        path_type, initial_parts = self._parse_path(first_part)

        # Add remaining parts
        all_parts = initial_parts
        for part in parts[1:]:
            if self._separator in part or "\\" in part:
                # Split on separator
                subparts = part.replace("\\", self._separator).split(self._separator)
                all_parts.extend(p for p in subparts if p)
            elif part:
                all_parts.append(part)

        # Create cache key
        cache_key = (path_type,) + tuple(all_parts)

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Determine starting root
        if path_type == "relative":
            current_idx = self.tree.relative_root
        elif path_type == "absolute":
            current_idx = self.tree.absolute_root
        elif path_type.startswith("drive:"):
            drive = path_type.split(":")[1]
            current_idx = self.tree.get_or_create_drive_root(drive)
        else:
            current_idx = self.tree.relative_root

        # Build path from root
        for part in all_parts:
            name_id = self.string_pool.intern(part)
            child_idx = self.tree.find_child(current_idx, name_id)
            if child_idx is None:
                child_idx = self.tree.add_node(current_idx, name_id)
            current_idx = child_idx

        # Cache the result
        self._cache[cache_key] = current_idx
        return current_idx

    def from_string(self, path: str) -> int:
        """Create or retrieve a path from a string representation."""
        return self.from_parts(path)

    def get_parts(self, node_idx: int) -> Tuple[str, ...]:
        """Get the path components for a node."""
        return tuple(self.tree.get_parts(node_idx))

    def get_parent(self, node_idx: int) -> Optional[int]:
        """Get the parent node index, or None for root."""
        if self.tree.is_root(node_idx):
            return None
        return self.tree.get_parent_idx(node_idx)

    def get_name(self, node_idx: int) -> str:
        """Get the name (last component) of a path."""
        if self.tree.is_root(node_idx):
            # For root nodes, return appropriate value
            root_type = self.tree.get_root_type(node_idx)
            if root_type == "absolute":
                return ""
            elif root_type.startswith("drive:"):
                return ""
            else:
                return ""
        name_id = self.tree.get_name_id(node_idx)
        return self.string_pool.get_string(name_id)

    def is_absolute(self, node_idx: int) -> bool:
        """Check if the path at this node is absolute."""
        root_type = self.tree.get_root_type(node_idx)
        return root_type == "absolute" or root_type.startswith("drive:")

    def join(self, base_idx: int, *parts: str) -> int:
        """Join additional parts to an existing path."""
        if not parts:
            return base_idx

        # Get base components
        base_parts = self.get_parts(base_idx)
        root_type = self.tree.get_root_type(base_idx)

        # Reconstruct the path with proper prefix
        if root_type == "absolute":
            combined = "/" + "/".join(base_parts) if base_parts else "/"
            new_path = combined.rstrip("/") + "/" + "/".join(parts)
        elif root_type.startswith("drive:"):
            drive = root_type.split(":")[1]
            combined = f"{drive}:/" + "/".join(base_parts) if base_parts else f"{drive}:"
            new_path = combined.rstrip("/") + "/" + "/".join(parts)
        else:
            # Relative path
            if base_parts:
                new_path = "/".join(base_parts) + "/" + "/".join(parts)
            else:
                new_path = "/".join(parts)

        return self.from_string(new_path)

    def stats(self) -> Dict[str, int]:
        """Return statistics about the allocator."""
        return {
            "strings_interned": len(self.string_pool),
            "nodes_allocated": len(self.tree.nodes),
            "cache_entries": len(self._cache),
            "relative_root": self.tree.relative_root,
            "absolute_root": self.tree.absolute_root,
            "drive_roots": len(self.tree.drive_roots),
        }