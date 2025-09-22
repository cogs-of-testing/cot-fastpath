#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>
#include <string.h>

/* ========================================================================
 * StringPool - Efficient string interning
 * ======================================================================== */

typedef struct {
    PyObject_HEAD
    PyObject *strings;      /* List of interned strings */
    PyObject *string_map;   /* Dict mapping strings to IDs */
} StringPoolObject;

static void
StringPool_dealloc(StringPoolObject *self)
{
    Py_XDECREF(self->strings);
    Py_XDECREF(self->string_map);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
StringPool_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    StringPoolObject *self;
    self = (StringPoolObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->strings = PyList_New(0);
        if (self->strings == NULL) {
            Py_DECREF(self);
            return NULL;
        }
        self->string_map = PyDict_New();
        if (self->string_map == NULL) {
            Py_DECREF(self);
            return NULL;
        }
    }
    return (PyObject *)self;
}

static PyObject *
StringPool_intern(StringPoolObject *self, PyObject *args)
{
    PyObject *s;
    if (!PyArg_ParseTuple(args, "U", &s))
        return NULL;

    /* Check if string already exists */
    PyObject *existing = PyDict_GetItem(self->string_map, s);
    if (existing != NULL) {
        Py_INCREF(existing);
        return existing;
    }

    /* Add new string */
    Py_ssize_t string_id = PyList_Size(self->strings);
    if (PyList_Append(self->strings, s) < 0)
        return NULL;

    PyObject *id_obj = PyLong_FromSsize_t(string_id);
    if (id_obj == NULL)
        return NULL;

    if (PyDict_SetItem(self->string_map, s, id_obj) < 0) {
        Py_DECREF(id_obj);
        return NULL;
    }

    return id_obj;
}

static PyObject *
StringPool_get_string(StringPoolObject *self, PyObject *args)
{
    Py_ssize_t string_id;
    if (!PyArg_ParseTuple(args, "n", &string_id))
        return NULL;

    PyObject *result = PyList_GetItem(self->strings, string_id);
    if (result == NULL)
        return NULL;

    Py_INCREF(result);
    return result;
}

static Py_ssize_t
StringPool_length(StringPoolObject *self)
{
    return PyList_Size(self->strings);
}

static PyMethodDef StringPool_methods[] = {
    {"intern", (PyCFunction)StringPool_intern, METH_VARARGS,
     "Intern a string and return its ID"},
    {"get_string", (PyCFunction)StringPool_get_string, METH_VARARGS,
     "Get the string associated with an ID"},
    {NULL}  /* Sentinel */
};

static PySequenceMethods StringPool_as_sequence = {
    (lenfunc)StringPool_length,  /* sq_length */
    0,  /* sq_concat */
    0,  /* sq_repeat */
    0,  /* sq_item */
    0,  /* sq_slice */
    0,  /* sq_ass_item */
    0,  /* sq_ass_slice */
    0,  /* sq_contains */
    0,  /* sq_inplace_concat */
    0,  /* sq_inplace_repeat */
};

static PyTypeObject StringPoolType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "fastpath._allocator_c.StringPool",
    .tp_doc = "String interning pool",
    .tp_basicsize = sizeof(StringPoolObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = StringPool_new,
    .tp_dealloc = (destructor)StringPool_dealloc,
    .tp_methods = StringPool_methods,
    .tp_as_sequence = &StringPool_as_sequence,
};

/* ========================================================================
 * TreeNode - Tree node structure
 * ======================================================================== */

typedef struct {
    Py_ssize_t parent_idx;
    Py_ssize_t name_id;
} TreeNode;

/* ========================================================================
 * TreeAllocator - Tree structure for paths
 * ======================================================================== */

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

static void
TreeAllocator_dealloc(TreeAllocatorObject *self)
{
    if (self->nodes) {
        PyMem_Free(self->nodes);
    }
    Py_XDECREF(self->string_pool);
    Py_XDECREF(self->drive_roots);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
TreeAllocator_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    TreeAllocatorObject *self;
    self = (TreeAllocatorObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->nodes = NULL;
        self->node_count = 0;
        self->node_capacity = 0;
        self->string_pool = NULL;
        self->relative_root = -1;
        self->absolute_root = -1;
        self->drive_roots = PyDict_New();
        if (self->drive_roots == NULL) {
            Py_DECREF(self);
            return NULL;
        }
    }
    return (PyObject *)self;
}

static int
TreeAllocator_init(TreeAllocatorObject *self, PyObject *args, PyObject *kwds)
{
    PyObject *string_pool;
    if (!PyArg_ParseTuple(args, "O", &string_pool))
        return -1;

    Py_INCREF(string_pool);
    self->string_pool = string_pool;

    /* Initialize nodes array */
    self->node_capacity = 128;
    self->nodes = PyMem_Malloc(self->node_capacity * sizeof(TreeNode));
    if (self->nodes == NULL) {
        PyErr_NoMemory();
        return -1;
    }

    /* Add root nodes */
    /* Relative root with empty string */
    PyObject *empty = PyUnicode_FromString("");
    PyObject *empty_id = PyObject_CallMethod(string_pool, "intern", "O", empty);
    Py_DECREF(empty);
    if (empty_id == NULL)
        return -1;

    self->nodes[0].parent_idx = -1;
    self->nodes[0].name_id = PyLong_AsLong(empty_id);
    Py_DECREF(empty_id);
    self->relative_root = 0;
    self->node_count = 1;

    /* Absolute root with "/" */
    PyObject *slash = PyUnicode_FromString("/");
    PyObject *slash_id = PyObject_CallMethod(string_pool, "intern", "O", slash);
    Py_DECREF(slash);
    if (slash_id == NULL)
        return -1;

    self->nodes[1].parent_idx = -1;
    self->nodes[1].name_id = PyLong_AsLong(slash_id);
    Py_DECREF(slash_id);
    self->absolute_root = 1;
    self->node_count = 2;

    return 0;
}

static Py_ssize_t
TreeAllocator_add_node(TreeAllocatorObject *self, Py_ssize_t parent_idx, Py_ssize_t name_id)
{
    /* Grow array if needed */
    if (self->node_count >= self->node_capacity) {
        Py_ssize_t new_capacity = self->node_capacity * 2;
        TreeNode *new_nodes = PyMem_Realloc(self->nodes, new_capacity * sizeof(TreeNode));
        if (new_nodes == NULL) {
            PyErr_NoMemory();
            return -1;
        }
        self->nodes = new_nodes;
        self->node_capacity = new_capacity;
    }

    Py_ssize_t node_idx = self->node_count;
    self->nodes[node_idx].parent_idx = parent_idx;
    self->nodes[node_idx].name_id = name_id;
    self->node_count++;

    return node_idx;
}

static PyObject *
TreeAllocator_add_node_py(TreeAllocatorObject *self, PyObject *args)
{
    Py_ssize_t parent_idx, name_id;
    if (!PyArg_ParseTuple(args, "nn", &parent_idx, &name_id))
        return NULL;

    Py_ssize_t node_idx = TreeAllocator_add_node(self, parent_idx, name_id);
    if (node_idx < 0)
        return NULL;

    return PyLong_FromSsize_t(node_idx);
}

static PyObject *
TreeAllocator_get_parts(TreeAllocatorObject *self, PyObject *args)
{
    Py_ssize_t node_idx;
    if (!PyArg_ParseTuple(args, "n", &node_idx))
        return NULL;

    if (node_idx < 0 || node_idx >= self->node_count) {
        PyErr_SetString(PyExc_IndexError, "Invalid node index");
        return NULL;
    }

    /* Count depth */
    Py_ssize_t depth = 0;
    Py_ssize_t curr = node_idx;
    while (self->nodes[curr].parent_idx >= 0) {
        depth++;
        curr = self->nodes[curr].parent_idx;
    }

    /* Build parts tuple */
    PyObject *parts = PyTuple_New(depth);
    if (parts == NULL)
        return NULL;

    curr = node_idx;
    for (Py_ssize_t i = depth - 1; i >= 0; i--) {
        PyObject *name_id = PyLong_FromSsize_t(self->nodes[curr].name_id);
        PyObject *name = PyObject_CallMethod(self->string_pool, "get_string", "O", name_id);
        Py_DECREF(name_id);
        if (name == NULL) {
            Py_DECREF(parts);
            return NULL;
        }
        PyTuple_SET_ITEM(parts, i, name);
        curr = self->nodes[curr].parent_idx;
    }

    return parts;
}

static PyObject *
TreeAllocator_find_child(TreeAllocatorObject *self, PyObject *args)
{
    Py_ssize_t parent_idx, name_id;
    if (!PyArg_ParseTuple(args, "nn", &parent_idx, &name_id))
        return NULL;

    /* Linear search through nodes */
    for (Py_ssize_t i = 0; i < self->node_count; i++) {
        if (self->nodes[i].parent_idx == parent_idx &&
            self->nodes[i].name_id == name_id) {
            return PyLong_FromSsize_t(i);
        }
    }

    Py_RETURN_NONE;
}

static PyObject *
TreeAllocator_get_parent_idx(TreeAllocatorObject *self, PyObject *args)
{
    Py_ssize_t node_idx;
    if (!PyArg_ParseTuple(args, "n", &node_idx))
        return NULL;

    if (node_idx < 0 || node_idx >= self->node_count) {
        PyErr_SetString(PyExc_IndexError, "Invalid node index");
        return NULL;
    }

    return PyLong_FromSsize_t(self->nodes[node_idx].parent_idx);
}

static PyObject *
TreeAllocator_get_root_type(TreeAllocatorObject *self, PyObject *args)
{
    Py_ssize_t node_idx;
    if (!PyArg_ParseTuple(args, "n", &node_idx))
        return NULL;

    if (node_idx == self->relative_root) {
        return PyUnicode_FromString("relative");
    } else if (node_idx == self->absolute_root) {
        return PyUnicode_FromString("absolute");
    }
    /* Check drive roots */
    PyObject *key, *value;
    Py_ssize_t pos = 0;
    while (PyDict_Next(self->drive_roots, &pos, &key, &value)) {
        if (PyLong_AsLong(value) == node_idx) {
            return PyUnicode_FromString("drive");
        }
    }
    return PyUnicode_FromString("unknown");
}

static PyObject *
TreeAllocator_is_root(TreeAllocatorObject *self, PyObject *args)
{
    Py_ssize_t node_idx;
    if (!PyArg_ParseTuple(args, "n", &node_idx))
        return NULL;

    if (node_idx == self->relative_root || node_idx == self->absolute_root) {
        Py_RETURN_TRUE;
    }

    /* Check drive roots */
    PyObject *key, *value;
    Py_ssize_t pos = 0;
    while (PyDict_Next(self->drive_roots, &pos, &key, &value)) {
        if (PyLong_AsLong(value) == node_idx) {
            Py_RETURN_TRUE;
        }
    }
    Py_RETURN_FALSE;
}

static PyObject *
TreeAllocator_get_name_id(TreeAllocatorObject *self, PyObject *args)
{
    Py_ssize_t node_idx;
    if (!PyArg_ParseTuple(args, "n", &node_idx))
        return NULL;

    if (node_idx < 0 || node_idx >= self->node_count) {
        PyErr_SetString(PyExc_IndexError, "Invalid node index");
        return NULL;
    }

    return PyLong_FromSsize_t(self->nodes[node_idx].name_id);
}

static PyMethodDef TreeAllocator_methods[] = {
    {"add_node", (PyCFunction)TreeAllocator_add_node_py, METH_VARARGS,
     "Add a new node to the tree"},
    {"get_parts", (PyCFunction)TreeAllocator_get_parts, METH_VARARGS,
     "Get path parts for a node"},
    {"find_child", (PyCFunction)TreeAllocator_find_child, METH_VARARGS,
     "Find a child node by parent and name"},
    {"get_parent_idx", (PyCFunction)TreeAllocator_get_parent_idx, METH_VARARGS,
     "Get parent index of a node"},
    {"get_root_type", (PyCFunction)TreeAllocator_get_root_type, METH_VARARGS,
     "Get root type of a path"},
    {"is_root", (PyCFunction)TreeAllocator_is_root, METH_VARARGS,
     "Check if node is a root"},
    {"get_name_id", (PyCFunction)TreeAllocator_get_name_id, METH_VARARGS,
     "Get name ID of a node"},
    {NULL}  /* Sentinel */
};

static PyMemberDef TreeAllocator_members[] = {
    {"string_pool", T_OBJECT_EX, offsetof(TreeAllocatorObject, string_pool), READONLY,
     "String pool"},
    {"relative_root", T_PYSSIZET, offsetof(TreeAllocatorObject, relative_root), READONLY,
     "Relative root index"},
    {"absolute_root", T_PYSSIZET, offsetof(TreeAllocatorObject, absolute_root), READONLY,
     "Absolute root index"},
    {"drive_roots", T_OBJECT_EX, offsetof(TreeAllocatorObject, drive_roots), READONLY,
     "Drive roots dictionary"},
    {NULL}  /* Sentinel */
};

static PyTypeObject TreeAllocatorType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "fastpath._allocator_c.TreeAllocator",
    .tp_doc = "Tree allocator for paths",
    .tp_basicsize = sizeof(TreeAllocatorObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = TreeAllocator_new,
    .tp_init = (initproc)TreeAllocator_init,
    .tp_dealloc = (destructor)TreeAllocator_dealloc,
    .tp_methods = TreeAllocator_methods,
    .tp_members = TreeAllocator_members,
};

/* ========================================================================
 * PathAllocator - Main allocator combining string pool and tree
 * ======================================================================== */

typedef struct {
    PyObject_HEAD
    StringPoolObject *string_pool;
    TreeAllocatorObject *tree;
    PyObject *cache;          /* LRU cache dict */
    const char *separator;    /* Path separator */
} PathAllocatorObject;

static void
PathAllocator_dealloc(PathAllocatorObject *self)
{
    Py_XDECREF(self->string_pool);
    Py_XDECREF(self->tree);
    Py_XDECREF(self->cache);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
PathAllocator_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PathAllocatorObject *self;
    self = (PathAllocatorObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->string_pool = NULL;
        self->tree = NULL;
        self->cache = NULL;
        self->separator = "/";
    }
    return (PyObject *)self;
}

static int
PathAllocator_init(PathAllocatorObject *self, PyObject *args, PyObject *kwds)
{
    const char *separator = "/";
    static char *kwlist[] = {"separator", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|s", kwlist, &separator))
        return -1;

    self->separator = separator;

    /* Create string pool */
    self->string_pool = (StringPoolObject *)PyObject_CallObject((PyObject *)&StringPoolType, NULL);
    if (self->string_pool == NULL)
        return -1;

    /* Create tree allocator */
    PyObject *tree_args = Py_BuildValue("(O)", self->string_pool);
    self->tree = (TreeAllocatorObject *)PyObject_CallObject((PyObject *)&TreeAllocatorType, tree_args);
    Py_DECREF(tree_args);
    if (self->tree == NULL)
        return -1;

    /* Create cache */
    self->cache = PyDict_New();
    if (self->cache == NULL)
        return -1;

    return 0;
}

static PyObject *
PathAllocator_from_parts(PathAllocatorObject *self, PyObject *args)
{
    /* Accept variable arguments */
    Py_ssize_t num_args = PyTuple_Size(args);
    PyObject *parts;

    /* Handle the case where all args are passed as parts */
    if (num_args == 1) {
        PyObject *first = PyTuple_GetItem(args, 0);
        if (PyTuple_Check(first)) {
            parts = first;
            Py_INCREF(parts);
        } else {
            parts = args;
            Py_INCREF(parts);
        }
    } else {
        parts = args;
        Py_INCREF(parts);
    }

    Py_ssize_t num_parts = PyTuple_Size(parts);
    if (num_parts == 0) {
        Py_DECREF(parts);
        return PyLong_FromSsize_t(self->tree->relative_root);
    }

    /* Determine root */
    Py_ssize_t current_idx;
    PyObject *first = PyTuple_GetItem(parts, 0);
    const char *first_str = PyUnicode_AsUTF8(first);

    if (first_str && first_str[0] == '/') {
        current_idx = self->tree->absolute_root;
    } else {
        current_idx = self->tree->relative_root;
    }

    /* Process each part */
    for (Py_ssize_t i = 0; i < num_parts; i++) {
        PyObject *part = PyTuple_GetItem(parts, i);
        if (part == NULL) {
            Py_DECREF(parts);
            return NULL;
        }

        /* Skip empty parts */
        if (PyUnicode_GetLength(part) == 0)
            continue;

        /* Intern the part */
        PyObject *intern_args = PyTuple_Pack(1, part);
        PyObject *name_id_obj = StringPool_intern(self->string_pool, intern_args);
        Py_DECREF(intern_args);
        if (name_id_obj == NULL) {
            Py_DECREF(parts);
            return NULL;
        }

        Py_ssize_t name_id = PyLong_AsLong(name_id_obj);
        Py_DECREF(name_id_obj);

        /* Find or create child node */
        PyObject *find_args = Py_BuildValue("(nn)", current_idx, name_id);
        PyObject *child_idx_obj = TreeAllocator_find_child(self->tree, find_args);
        Py_DECREF(find_args);

        if (child_idx_obj == Py_None) {
            Py_DECREF(child_idx_obj);
            current_idx = TreeAllocator_add_node(self->tree, current_idx, name_id);
            if (current_idx < 0) {
                Py_DECREF(parts);
                return NULL;
            }
        } else {
            current_idx = PyLong_AsLong(child_idx_obj);
            Py_DECREF(child_idx_obj);
        }
    }

    Py_DECREF(parts);
    return PyLong_FromSsize_t(current_idx);
}

static PyObject *
PathAllocator_get_parts(PathAllocatorObject *self, PyObject *args)
{
    Py_ssize_t node_idx;
    if (!PyArg_ParseTuple(args, "n", &node_idx))
        return NULL;

    PyObject *tree_args = Py_BuildValue("(n)", node_idx);
    PyObject *result = TreeAllocator_get_parts(self->tree, tree_args);
    Py_DECREF(tree_args);

    return result;
}

static PyObject *
PathAllocator_get_parent(PathAllocatorObject *self, PyObject *args)
{
    Py_ssize_t node_idx;
    if (!PyArg_ParseTuple(args, "n", &node_idx))
        return NULL;

    if (node_idx < 0 || node_idx >= self->tree->node_count) {
        PyErr_SetString(PyExc_IndexError, "Invalid node index");
        return NULL;
    }

    Py_ssize_t parent_idx = self->tree->nodes[node_idx].parent_idx;
    if (parent_idx < 0) {
        return PyLong_FromSsize_t(node_idx);  /* Root is its own parent */
    }

    return PyLong_FromSsize_t(parent_idx);
}

static PyObject *
PathAllocator_get_name(PathAllocatorObject *self, PyObject *args)
{
    Py_ssize_t node_idx;
    if (!PyArg_ParseTuple(args, "n", &node_idx))
        return NULL;

    if (node_idx < 0 || node_idx >= self->tree->node_count) {
        PyErr_SetString(PyExc_IndexError, "Invalid node index");
        return NULL;
    }

    Py_ssize_t name_id = self->tree->nodes[node_idx].name_id;
    PyObject *name_id_obj = PyLong_FromSsize_t(name_id);
    PyObject *get_args = Py_BuildValue("(O)", name_id_obj);
    PyObject *result = StringPool_get_string(self->string_pool, get_args);
    Py_DECREF(get_args);
    Py_DECREF(name_id_obj);

    return result;
}

static PyObject *
PathAllocator_from_string(PathAllocatorObject *self, PyObject *args)
{
    const char *path_str;
    if (!PyArg_ParseTuple(args, "s", &path_str))
        return NULL;

    /* Split path by separator and call from_parts */
    PyObject *parts_list = PyList_New(0);
    if (parts_list == NULL)
        return NULL;

    char *path_copy = strdup(path_str);
    char *token = strtok(path_copy, self->separator);
    while (token != NULL) {
        PyObject *part = PyUnicode_FromString(token);
        if (PyList_Append(parts_list, part) < 0) {
            Py_DECREF(part);
            Py_DECREF(parts_list);
            free(path_copy);
            return NULL;
        }
        Py_DECREF(part);
        token = strtok(NULL, self->separator);
    }
    free(path_copy);

    /* Convert list to tuple */
    PyObject *parts_tuple = PyList_AsTuple(parts_list);
    Py_DECREF(parts_list);
    if (parts_tuple == NULL)
        return NULL;

    /* Call from_parts */
    PyObject *result = PathAllocator_from_parts(self, parts_tuple);
    Py_DECREF(parts_tuple);
    return result;
}

static PyObject *
PathAllocator_join(PathAllocatorObject *self, PyObject *args)
{
    Py_ssize_t base_idx;
    PyObject *parts;

    /* Parse base_idx and remaining args as parts */
    if (PyTuple_Size(args) < 1) {
        PyErr_SetString(PyExc_TypeError, "join() missing required argument: 'base_idx'");
        return NULL;
    }

    PyObject *first = PyTuple_GetItem(args, 0);
    base_idx = PyLong_AsLong(first);
    if (PyErr_Occurred())
        return NULL;

    /* Get base parts */
    PyObject *get_args = Py_BuildValue("(n)", base_idx);
    PyObject *base_parts = PathAllocator_get_parts(self, get_args);
    Py_DECREF(get_args);
    if (base_parts == NULL)
        return NULL;

    /* Combine with new parts */
    Py_ssize_t base_len = PyTuple_Size(base_parts);
    Py_ssize_t new_len = PyTuple_Size(args) - 1;
    PyObject *combined = PyTuple_New(base_len + new_len);

    /* Copy base parts */
    for (Py_ssize_t i = 0; i < base_len; i++) {
        PyObject *item = PyTuple_GetItem(base_parts, i);
        Py_INCREF(item);
        PyTuple_SET_ITEM(combined, i, item);
    }

    /* Copy new parts */
    for (Py_ssize_t i = 1; i < PyTuple_Size(args); i++) {
        PyObject *item = PyTuple_GetItem(args, i);
        Py_INCREF(item);
        PyTuple_SET_ITEM(combined, base_len + i - 1, item);
    }

    Py_DECREF(base_parts);

    /* Call from_parts */
    PyObject *result = PathAllocator_from_parts(self, combined);
    Py_DECREF(combined);
    return result;
}

static PyObject *
PathAllocator_stats(PathAllocatorObject *self, PyObject *args)
{
    PyObject *dict = PyDict_New();
    if (dict == NULL)
        return NULL;

    PyDict_SetItemString(dict, "string_count", PyLong_FromSsize_t(PyList_Size(self->string_pool->strings)));
    PyDict_SetItemString(dict, "node_count", PyLong_FromSsize_t(self->tree->node_count));
    PyDict_SetItemString(dict, "cache_size", PyLong_FromSsize_t(PyDict_Size(self->cache)));

    return dict;
}

static PyObject *
PathAllocator_is_absolute(PathAllocatorObject *self, PyObject *args)
{
    Py_ssize_t node_idx;
    if (!PyArg_ParseTuple(args, "n", &node_idx))
        return NULL;

    /* Walk up to root */
    Py_ssize_t current = node_idx;
    while (current >= 0 && self->tree->nodes[current].parent_idx >= 0) {
        current = self->tree->nodes[current].parent_idx;
    }

    if (current == self->tree->absolute_root) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

static PyMethodDef PathAllocator_methods[] = {
    {"from_parts", (PyCFunction)PathAllocator_from_parts, METH_VARARGS,
     "Create path from parts"},
    {"from_string", (PyCFunction)PathAllocator_from_string, METH_VARARGS,
     "Create path from string"},
    {"get_parts", (PyCFunction)PathAllocator_get_parts, METH_VARARGS,
     "Get parts of a path"},
    {"get_parent", (PyCFunction)PathAllocator_get_parent, METH_VARARGS,
     "Get parent node index"},
    {"get_name", (PyCFunction)PathAllocator_get_name, METH_VARARGS,
     "Get name of a node"},
    {"join", (PyCFunction)PathAllocator_join, METH_VARARGS,
     "Join path parts"},
    {"stats", (PyCFunction)PathAllocator_stats, METH_NOARGS,
     "Get allocator statistics"},
    {"is_absolute", (PyCFunction)PathAllocator_is_absolute, METH_VARARGS,
     "Check if path is absolute"},
    {NULL}  /* Sentinel */
};

static PyMemberDef PathAllocator_members[] = {
    {"string_pool", T_OBJECT_EX, offsetof(PathAllocatorObject, string_pool), READONLY,
     "String pool"},
    {"tree", T_OBJECT_EX, offsetof(PathAllocatorObject, tree), READONLY,
     "Tree allocator"},
    {NULL}  /* Sentinel */
};

static PyTypeObject PathAllocatorType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "fastpath._allocator_c.PathAllocator",
    .tp_doc = "Path allocator",
    .tp_basicsize = sizeof(PathAllocatorObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = PathAllocator_new,
    .tp_init = (initproc)PathAllocator_init,
    .tp_dealloc = (destructor)PathAllocator_dealloc,
    .tp_methods = PathAllocator_methods,
    .tp_members = PathAllocator_members,
};

/* ========================================================================
 * Module initialization
 * ======================================================================== */

static PyModuleDef allocatormodule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_allocator_c",
    .m_doc = "C implementation of path allocator",
    .m_size = -1,
};

PyMODINIT_FUNC
PyInit__allocator_c(void)
{
    PyObject *m;

    if (PyType_Ready(&StringPoolType) < 0)
        return NULL;

    if (PyType_Ready(&TreeAllocatorType) < 0)
        return NULL;

    if (PyType_Ready(&PathAllocatorType) < 0)
        return NULL;

    m = PyModule_Create(&allocatormodule);
    if (m == NULL)
        return NULL;

    Py_INCREF(&StringPoolType);
    if (PyModule_AddObject(m, "StringPool", (PyObject *)&StringPoolType) < 0) {
        Py_DECREF(&StringPoolType);
        Py_DECREF(m);
        return NULL;
    }

    Py_INCREF(&TreeAllocatorType);
    if (PyModule_AddObject(m, "TreeAllocator", (PyObject *)&TreeAllocatorType) < 0) {
        Py_DECREF(&TreeAllocatorType);
        Py_DECREF(m);
        return NULL;
    }

    Py_INCREF(&PathAllocatorType);
    if (PyModule_AddObject(m, "PathAllocator", (PyObject *)&PathAllocatorType) < 0) {
        Py_DECREF(&PathAllocatorType);
        Py_DECREF(m);
        return NULL;
    }

    /* Add ROOT_PARENT constant */
    if (PyModule_AddIntConstant(m, "ROOT_PARENT", -1) < 0) {
        Py_DECREF(m);
        return NULL;
    }

    return m;
}