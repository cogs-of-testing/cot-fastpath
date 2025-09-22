#ifndef FASTPATH_H
#define FASTPATH_H

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>
#include <string.h>
#include <stdbool.h>

/* ========================================================================
 * Type definitions
 * ======================================================================== */

/* TreeNode structure */
typedef struct {
    Py_ssize_t parent_idx;
    Py_ssize_t name_id;
} TreeNode;

/* StringPool object */
typedef struct {
    PyObject_HEAD
    PyObject *strings;      /* List of interned strings */
    PyObject *string_map;   /* Dict mapping strings to IDs */
} StringPoolObject;

/* TreeAllocator object */
typedef struct {
    PyObject_HEAD
    TreeNode *nodes;           /* Array of nodes */
    Py_ssize_t node_count;     /* Number of nodes */
    Py_ssize_t node_capacity;  /* Capacity of nodes array */
    PyObject *string_pool;     /* Reference to string pool */
    Py_ssize_t relative_root;  /* Index of relative root */
    Py_ssize_t absolute_root;  /* Index of absolute root */
    PyObject *drive_roots;     /* Dict of drive roots */
} TreeAllocatorObject;

/* PathAllocator object */
typedef struct {
    PyObject_HEAD
    StringPoolObject *string_pool;
    TreeAllocatorObject *tree;
    PyObject *cache;          /* LRU cache dict */
    const char *separator;    /* Path separator */
} PathAllocatorObject;

/* PureFastPath object */
typedef struct {
    PyObject_HEAD
    PyObject *_allocator;  /* PathAllocator instance */
    Py_ssize_t _node_idx;  /* Node index in tree */
} PureFastPathObject;

/* FastPath object */
typedef struct {
    PureFastPathObject base;  /* Inherits from PureFastPath */
} FastPathObject;

/* ========================================================================
 * Global variables
 * ======================================================================== */

extern PyTypeObject StringPoolType;
extern PyTypeObject TreeAllocatorType;
extern PyTypeObject PathAllocatorType;
extern PyTypeObject PureFastPathType;
extern PyTypeObject FastPathType;

extern PyObject *default_allocator;

/* ========================================================================
 * Function declarations
 * ======================================================================== */

/* StringPool methods */
PyObject* StringPool_intern(StringPoolObject *self, PyObject *args);
PyObject* StringPool_get_string(StringPoolObject *self, PyObject *args);

/* TreeAllocator methods */
Py_ssize_t TreeAllocator_add_node(TreeAllocatorObject *self, Py_ssize_t parent_idx, Py_ssize_t name_id);
PyObject* TreeAllocator_add_node_py(TreeAllocatorObject *self, PyObject *args);
PyObject* TreeAllocator_get_parts(TreeAllocatorObject *self, PyObject *args);
PyObject* TreeAllocator_find_child(TreeAllocatorObject *self, PyObject *args);

/* PathAllocator methods */
PyObject* PathAllocator_from_parts(PathAllocatorObject *self, PyObject *args);
PyObject* PathAllocator_from_string(PathAllocatorObject *self, PyObject *args);
PyObject* PathAllocator_get_parts(PathAllocatorObject *self, PyObject *args);
PyObject* PathAllocator_get_parent(PathAllocatorObject *self, PyObject *args);
PyObject* PathAllocator_get_name(PathAllocatorObject *self, PyObject *args);

/* PureFastPath methods */
PyObject* PureFastPath_str(PureFastPathObject *self);
PyObject* PureFastPath_get_parent(PureFastPathObject *self, void *closure);
PyObject* PureFastPath_get_name(PureFastPathObject *self, void *closure);
PyObject* PureFastPath_truediv(PureFastPathObject *self, PyObject *other);

/* Helper functions */
PyObject* get_default_allocator(void);

#endif /* FASTPATH_H */