#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>
#include <string.h>
#include <stdbool.h>

/* Forward declarations */
static PyTypeObject PureFastPathType;
static PyTypeObject FastPathType;

/* Import allocator types */
static PyObject *allocator_module = NULL;
static PyObject *PathAllocator_Type = NULL;

/* Global default allocator */
static PyObject *default_allocator = NULL;

/* ========================================================================
 * PureFastPath - Pure path implementation
 * ======================================================================== */

typedef struct {
    PyObject_HEAD
    PyObject *_allocator;  /* PathAllocator instance */
    Py_ssize_t _node_idx;  /* Node index in tree */
} PureFastPathObject;

static void
PureFastPath_dealloc(PureFastPathObject *self)
{
    Py_XDECREF(self->_allocator);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
PureFastPath_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PureFastPathObject *self;
    self = (PureFastPathObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->_allocator = NULL;
        self->_node_idx = -1;
    }
    return (PyObject *)self;
}

static PyObject *
get_default_allocator(void)
{
    if (default_allocator == NULL) {
        /* Create default allocator */
        default_allocator = PyObject_CallObject(PathAllocator_Type, NULL);
    }
    Py_XINCREF(default_allocator);
    return default_allocator;
}

static int
PureFastPath_init(PureFastPathObject *self, PyObject *args, PyObject *kwds)
{
    PyObject *allocator = NULL;
    Py_ssize_t node_idx = -1;
    PyObject *parts = NULL;
    static char *kwlist[] = {"allocator", "_node_idx", NULL};

    /* First try to parse with keywords for internal use */
    if (PyTuple_Size(args) == 0 && kwds != NULL) {
        if (!PyArg_ParseTupleAndKeywords(args, kwds, "|On", kwlist, &allocator, &node_idx))
            return -1;

        if (node_idx >= 0) {
            /* Internal creation with node_idx */
            if (allocator == NULL) {
                allocator = get_default_allocator();
            } else {
                Py_INCREF(allocator);
            }
            self->_allocator = allocator;
            self->_node_idx = node_idx;
            return 0;
        }
    }

    /* Normal creation from path parts */
    if (allocator == NULL) {
        allocator = get_default_allocator();
    } else {
        Py_INCREF(allocator);
    }
    self->_allocator = allocator;

    /* Handle single string argument - use from_string */
    if (PyTuple_Size(args) == 1) {
        PyObject *first = PyTuple_GetItem(args, 0);
        if (PyUnicode_Check(first)) {
            /* It's a path string, use from_string */
            PyObject *from_string = PyObject_GetAttrString(allocator, "from_string");
            if (from_string == NULL) {
                return -1;
            }

            PyObject *result = PyObject_Call(from_string, args, NULL);
            Py_DECREF(from_string);
            if (result == NULL) {
                return -1;
            }

            self->_node_idx = PyLong_AsLong(result);
            Py_DECREF(result);
            return 0;
        }
    }

    /* Call allocator.from_parts with the provided parts */
    PyObject *from_parts = PyObject_GetAttrString(allocator, "from_parts");
    if (from_parts == NULL) {
        return -1;
    }

    PyObject *result = PyObject_Call(from_parts, args, NULL);
    Py_DECREF(from_parts);
    if (result == NULL) {
        return -1;
    }

    self->_node_idx = PyLong_AsLong(result);
    Py_DECREF(result);

    return 0;
}

static PyObject *
PureFastPath_str(PureFastPathObject *self)
{
    /* Get parts from allocator */
    PyObject *get_parts = PyObject_GetAttrString(self->_allocator, "get_parts");
    if (get_parts == NULL)
        return NULL;

    PyObject *args = Py_BuildValue("(n)", self->_node_idx);
    PyObject *parts = PyObject_Call(get_parts, args, NULL);
    Py_DECREF(args);
    Py_DECREF(get_parts);

    if (parts == NULL)
        return NULL;

    /* Get separator */
    PyObject *separator = PyObject_GetAttrString(self->_allocator, "_separator");
    if (separator == NULL) {
        separator = PyUnicode_FromString("/");
    }

    /* Join parts with separator */
    PyObject *result = PyUnicode_Join(separator, parts);
    Py_DECREF(separator);
    Py_DECREF(parts);

    return result;
}

static PyObject *
PureFastPath_repr(PureFastPathObject *self)
{
    PyObject *str_repr = PureFastPath_str(self);
    if (str_repr == NULL)
        return NULL;

    PyObject *result = PyUnicode_FromFormat("PureFastPath(%R)", str_repr);
    Py_DECREF(str_repr);
    return result;
}

static PyObject *
PureFastPath_truediv(PureFastPathObject *self, PyObject *other)
{
    /* Handle path joining with / operator */
    PyObject *join_method = PyObject_GetAttrString(self->_allocator, "join");
    if (join_method == NULL)
        return NULL;

    PyObject *args;
    if (PyUnicode_Check(other)) {
        args = Py_BuildValue("(nO)", self->_node_idx, other);
    } else {
        Py_DECREF(join_method);
        PyErr_SetString(PyExc_TypeError, "unsupported operand type(s) for /");
        return NULL;
    }

    PyObject *new_idx = PyObject_Call(join_method, args, NULL);
    Py_DECREF(args);
    Py_DECREF(join_method);

    if (new_idx == NULL)
        return NULL;

    /* Create new path object with the new index */
    PyObject *kwargs = Py_BuildValue("{s:O,s:O}",
        "allocator", self->_allocator,
        "_node_idx", new_idx);
    PyObject *new_path = PyObject_Call((PyObject *)Py_TYPE(self), PyTuple_New(0), kwargs);
    Py_DECREF(kwargs);
    Py_DECREF(new_idx);

    return new_path;
}

static PyObject *
PureFastPath_get_parts(PureFastPathObject *self, void *closure)
{
    PyObject *get_parts = PyObject_GetAttrString(self->_allocator, "get_parts");
    if (get_parts == NULL)
        return NULL;

    PyObject *args = Py_BuildValue("(n)", self->_node_idx);
    PyObject *result = PyObject_Call(get_parts, args, NULL);
    Py_DECREF(args);
    Py_DECREF(get_parts);

    return result;
}

static PyObject *
PureFastPath_get_parent(PureFastPathObject *self, void *closure)
{
    PyObject *get_parent = PyObject_GetAttrString(self->_allocator, "get_parent");
    if (get_parent == NULL)
        return NULL;

    PyObject *args = Py_BuildValue("(n)", self->_node_idx);
    PyObject *parent_idx = PyObject_Call(get_parent, args, NULL);
    Py_DECREF(args);
    Py_DECREF(get_parent);

    if (parent_idx == NULL)
        return NULL;

    /* Create new path with parent index */
    PyObject *kwargs = Py_BuildValue("{s:O,s:O}",
        "allocator", self->_allocator,
        "_node_idx", parent_idx);
    PyObject *new_path = PyObject_Call((PyObject *)Py_TYPE(self), PyTuple_New(0), kwargs);
    Py_DECREF(kwargs);
    Py_DECREF(parent_idx);

    return new_path;
}

static PyObject *
PureFastPath_get_name(PureFastPathObject *self, void *closure)
{
    PyObject *get_name = PyObject_GetAttrString(self->_allocator, "get_name");
    if (get_name == NULL)
        return NULL;

    PyObject *args = Py_BuildValue("(n)", self->_node_idx);
    PyObject *result = PyObject_Call(get_name, args, NULL);
    Py_DECREF(args);
    Py_DECREF(get_name);

    return result;
}

static PyObject *
PureFastPath_get_stem(PureFastPathObject *self, void *closure)
{
    PyObject *name = PureFastPath_get_name(self, NULL);
    if (name == NULL)
        return NULL;

    /* Find the last dot */
    Py_ssize_t name_len = PyUnicode_GetLength(name);
    const char *name_str = PyUnicode_AsUTF8(name);

    const char *dot = strrchr(name_str, '.');
    if (dot == NULL || dot == name_str) {
        /* No extension or hidden file */
        return name;
    }

    Py_ssize_t stem_len = dot - name_str;
    PyObject *stem = PyUnicode_FromStringAndSize(name_str, stem_len);
    Py_DECREF(name);
    return stem;
}

static PyObject *
PureFastPath_get_suffix(PureFastPathObject *self, void *closure)
{
    PyObject *name = PureFastPath_get_name(self, NULL);
    if (name == NULL)
        return NULL;

    const char *name_str = PyUnicode_AsUTF8(name);
    const char *dot = strrchr(name_str, '.');

    PyObject *result;
    if (dot == NULL || dot == name_str) {
        /* No extension or hidden file */
        result = PyUnicode_FromString("");
    } else {
        result = PyUnicode_FromString(dot);
    }

    Py_DECREF(name);
    return result;
}

static PyObject *
PureFastPath_is_absolute(PureFastPathObject *self, PyObject *Py_UNUSED(ignored))
{
    PyObject *is_absolute = PyObject_GetAttrString(self->_allocator, "is_absolute");
    if (is_absolute == NULL)
        return NULL;

    PyObject *args = Py_BuildValue("(n)", self->_node_idx);
    PyObject *result = PyObject_Call(is_absolute, args, NULL);
    Py_DECREF(args);
    Py_DECREF(is_absolute);

    return result;
}

static PyObject *
PureFastPath_joinpath(PureFastPathObject *self, PyObject *args)
{
    /* Join multiple path parts */
    if (PyTuple_Size(args) == 0) {
        Py_INCREF(self);
        return (PyObject *)self;
    }

    PyObject *current = (PyObject *)self;
    Py_INCREF(current);

    for (Py_ssize_t i = 0; i < PyTuple_Size(args); i++) {
        PyObject *part = PyTuple_GetItem(args, i);
        PyObject *next = PureFastPath_truediv((PureFastPathObject *)current, part);
        Py_DECREF(current);
        if (next == NULL)
            return NULL;
        current = next;
    }

    return current;
}

static PyObject *
PureFastPath_with_name(PureFastPathObject *self, PyObject *args)
{
    const char *name;
    if (!PyArg_ParseTuple(args, "s", &name))
        return NULL;

    /* Get parent and join with new name */
    PyObject *parent = PureFastPath_get_parent(self, NULL);
    if (parent == NULL)
        return NULL;

    PyObject *name_obj = PyUnicode_FromString(name);
    PyObject *result = PureFastPath_truediv((PureFastPathObject *)parent, name_obj);
    Py_DECREF(parent);
    Py_DECREF(name_obj);

    return result;
}

static PyObject *
PureFastPath_with_suffix(PureFastPathObject *self, PyObject *args)
{
    const char *suffix;
    if (!PyArg_ParseTuple(args, "s", &suffix))
        return NULL;

    /* Get stem and append new suffix */
    PyObject *stem = PureFastPath_get_stem(self, NULL);
    if (stem == NULL)
        return NULL;

    PyObject *new_name = PyUnicode_FromFormat("%U%s", stem, suffix);
    Py_DECREF(stem);

    PyObject *result_args = Py_BuildValue("(O)", new_name);
    PyObject *result = PureFastPath_with_name(self, result_args);
    Py_DECREF(result_args);
    Py_DECREF(new_name);

    return result;
}

static Py_hash_t
PureFastPath_hash(PureFastPathObject *self)
{
    /* Hash based on allocator and node index */
    return PyObject_Hash(self->_allocator) ^ self->_node_idx;
}

static PyObject *
PureFastPath_richcompare(PureFastPathObject *self, PyObject *other, int op)
{
    if (!PyObject_IsInstance(other, (PyObject *)&PureFastPathType)) {
        Py_RETURN_NOTIMPLEMENTED;
    }

    PureFastPathObject *other_path = (PureFastPathObject *)other;

    /* For equality, check allocator and node index */
    if (op == Py_EQ) {
        if (self->_allocator == other_path->_allocator &&
            self->_node_idx == other_path->_node_idx) {
            Py_RETURN_TRUE;
        }
        Py_RETURN_FALSE;
    } else if (op == Py_NE) {
        if (self->_allocator != other_path->_allocator ||
            self->_node_idx != other_path->_node_idx) {
            Py_RETURN_TRUE;
        }
        Py_RETURN_FALSE;
    }

    /* For other comparisons, compare string representations */
    PyObject *self_str = PureFastPath_str(self);
    PyObject *other_str = PureFastPath_str(other_path);

    if (self_str == NULL || other_str == NULL) {
        Py_XDECREF(self_str);
        Py_XDECREF(other_str);
        return NULL;
    }

    PyObject *result = PyObject_RichCompare(self_str, other_str, op);
    Py_DECREF(self_str);
    Py_DECREF(other_str);

    return result;
}

static PyMethodDef PureFastPath_methods[] = {
    {"is_absolute", (PyCFunction)PureFastPath_is_absolute, METH_NOARGS,
     "Return True if the path is absolute"},
    {"joinpath", (PyCFunction)PureFastPath_joinpath, METH_VARARGS,
     "Join one or more path components"},
    {"with_name", (PyCFunction)PureFastPath_with_name, METH_VARARGS,
     "Return a new path with the file name changed"},
    {"with_suffix", (PyCFunction)PureFastPath_with_suffix, METH_VARARGS,
     "Return a new path with the suffix changed"},
    {NULL}  /* Sentinel */
};

static PyGetSetDef PureFastPath_getsetters[] = {
    {"parts", (getter)PureFastPath_get_parts, NULL,
     "Tuple of path components", NULL},
    {"parent", (getter)PureFastPath_get_parent, NULL,
     "The parent directory", NULL},
    {"name", (getter)PureFastPath_get_name, NULL,
     "The final component", NULL},
    {"stem", (getter)PureFastPath_get_stem, NULL,
     "The final component without suffix", NULL},
    {"suffix", (getter)PureFastPath_get_suffix, NULL,
     "The file extension", NULL},
    {NULL}  /* Sentinel */
};

static PyNumberMethods PureFastPath_as_number = {
    0,  /* nb_add */
    0,  /* nb_subtract */
    0,  /* nb_multiply */
    0,  /* nb_remainder */
    0,  /* nb_divmod */
    0,  /* nb_power */
    0,  /* nb_negative */
    0,  /* nb_positive */
    0,  /* nb_absolute */
    0,  /* nb_bool */
    0,  /* nb_invert */
    0,  /* nb_lshift */
    0,  /* nb_rshift */
    0,  /* nb_and */
    0,  /* nb_xor */
    0,  /* nb_or */
    0,  /* nb_int */
    0,  /* nb_reserved */
    0,  /* nb_float */
    0,  /* nb_inplace_add */
    0,  /* nb_inplace_subtract */
    0,  /* nb_inplace_multiply */
    0,  /* nb_inplace_remainder */
    0,  /* nb_inplace_power */
    0,  /* nb_inplace_lshift */
    0,  /* nb_inplace_rshift */
    0,  /* nb_inplace_and */
    0,  /* nb_inplace_xor */
    0,  /* nb_inplace_or */
    0,  /* nb_floor_divide */
    (binaryfunc)PureFastPath_truediv,  /* nb_true_divide */
    0,  /* nb_inplace_floor_divide */
    0,  /* nb_inplace_true_divide */
};

static PyTypeObject PureFastPathType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "fastpath._path_c.PureFastPath",
    .tp_doc = "Pure fast path implementation",
    .tp_basicsize = sizeof(PureFastPathObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = PureFastPath_new,
    .tp_init = (initproc)PureFastPath_init,
    .tp_dealloc = (destructor)PureFastPath_dealloc,
    .tp_repr = (reprfunc)PureFastPath_repr,
    .tp_str = (reprfunc)PureFastPath_str,
    .tp_hash = (hashfunc)PureFastPath_hash,
    .tp_richcompare = (richcmpfunc)PureFastPath_richcompare,
    .tp_methods = PureFastPath_methods,
    .tp_getset = PureFastPath_getsetters,
    .tp_as_number = &PureFastPath_as_number,
};

/* ========================================================================
 * FastPath - Concrete path with filesystem operations
 * ======================================================================== */

typedef struct {
    PureFastPathObject base;  /* Inherits from PureFastPath */
} FastPathObject;

static PyObject *
FastPath_exists(FastPathObject *self, PyObject *Py_UNUSED(ignored))
{
    /* Get string representation of path */
    PyObject *path_str = PureFastPath_str((PureFastPathObject *)self);
    if (path_str == NULL)
        return NULL;

    /* Use os.path.exists */
    PyObject *os_path = PyImport_ImportModule("os.path");
    if (os_path == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *exists = PyObject_GetAttrString(os_path, "exists");
    Py_DECREF(os_path);
    if (exists == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *args = Py_BuildValue("(O)", path_str);
    PyObject *result = PyObject_Call(exists, args, NULL);
    Py_DECREF(args);
    Py_DECREF(exists);
    Py_DECREF(path_str);

    return result;
}

static PyObject *
FastPath_is_file(FastPathObject *self, PyObject *Py_UNUSED(ignored))
{
    PyObject *path_str = PureFastPath_str((PureFastPathObject *)self);
    if (path_str == NULL)
        return NULL;

    PyObject *os_path = PyImport_ImportModule("os.path");
    if (os_path == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *isfile = PyObject_GetAttrString(os_path, "isfile");
    Py_DECREF(os_path);
    if (isfile == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *args = Py_BuildValue("(O)", path_str);
    PyObject *result = PyObject_Call(isfile, args, NULL);
    Py_DECREF(args);
    Py_DECREF(isfile);
    Py_DECREF(path_str);

    return result;
}

static PyObject *
FastPath_is_dir(FastPathObject *self, PyObject *Py_UNUSED(ignored))
{
    PyObject *path_str = PureFastPath_str((PureFastPathObject *)self);
    if (path_str == NULL)
        return NULL;

    PyObject *os_path = PyImport_ImportModule("os.path");
    if (os_path == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *isdir = PyObject_GetAttrString(os_path, "isdir");
    Py_DECREF(os_path);
    if (isdir == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *args = Py_BuildValue("(O)", path_str);
    PyObject *result = PyObject_Call(isdir, args, NULL);
    Py_DECREF(args);
    Py_DECREF(isdir);
    Py_DECREF(path_str);

    return result;
}

static PyObject *
FastPath_read_text(FastPathObject *self, PyObject *args, PyObject *kwds)
{
    const char *encoding = "utf-8";
    static char *kwlist[] = {"encoding", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|s", kwlist, &encoding))
        return NULL;

    PyObject *path_str = PureFastPath_str((PureFastPathObject *)self);
    if (path_str == NULL)
        return NULL;

    /* Open and read file */
    PyObject *io_module = PyImport_ImportModule("io");
    if (io_module == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *open_func = PyObject_GetAttrString(io_module, "open");
    Py_DECREF(io_module);
    if (open_func == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *open_args = Py_BuildValue("(Os)", path_str, "r");
    PyObject *open_kwargs = Py_BuildValue("{s:s}", "encoding", encoding);
    PyObject *file = PyObject_Call(open_func, open_args, open_kwargs);
    Py_DECREF(open_func);
    Py_DECREF(open_args);
    Py_DECREF(open_kwargs);
    Py_DECREF(path_str);

    if (file == NULL)
        return NULL;

    /* Read content */
    PyObject *read_method = PyObject_GetAttrString(file, "read");
    if (read_method == NULL) {
        Py_DECREF(file);
        return NULL;
    }

    PyObject *content = PyObject_CallObject(read_method, NULL);
    Py_DECREF(read_method);

    /* Close file */
    PyObject *close_method = PyObject_GetAttrString(file, "close");
    if (close_method != NULL) {
        PyObject_CallObject(close_method, NULL);
        Py_DECREF(close_method);
    }
    Py_DECREF(file);

    return content;
}

static PyObject *
FastPath_write_text(FastPathObject *self, PyObject *args, PyObject *kwds)
{
    const char *data;
    const char *encoding = "utf-8";
    static char *kwlist[] = {"data", "encoding", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|s", kwlist, &data, &encoding))
        return NULL;

    PyObject *path_str = PureFastPath_str((PureFastPathObject *)self);
    if (path_str == NULL)
        return NULL;

    /* Open and write file */
    PyObject *io_module = PyImport_ImportModule("io");
    if (io_module == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *open_func = PyObject_GetAttrString(io_module, "open");
    Py_DECREF(io_module);
    if (open_func == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *open_args = Py_BuildValue("(Os)", path_str, "w");
    PyObject *open_kwargs = Py_BuildValue("{s:s}", "encoding", encoding);
    PyObject *file = PyObject_Call(open_func, open_args, open_kwargs);
    Py_DECREF(open_func);
    Py_DECREF(open_args);
    Py_DECREF(open_kwargs);
    Py_DECREF(path_str);

    if (file == NULL)
        return NULL;

    /* Write content */
    PyObject *write_method = PyObject_GetAttrString(file, "write");
    if (write_method == NULL) {
        Py_DECREF(file);
        return NULL;
    }

    PyObject *write_args = Py_BuildValue("(s)", data);
    PyObject *bytes_written = PyObject_Call(write_method, write_args, NULL);
    Py_DECREF(write_method);
    Py_DECREF(write_args);

    /* Close file */
    PyObject *close_method = PyObject_GetAttrString(file, "close");
    if (close_method != NULL) {
        PyObject_CallObject(close_method, NULL);
        Py_DECREF(close_method);
    }
    Py_DECREF(file);

    if (bytes_written == NULL)
        return NULL;

    Py_DECREF(bytes_written);
    Py_RETURN_NONE;
}

static PyObject *
FastPath_mkdir(FastPathObject *self, PyObject *args, PyObject *kwds)
{
    int parents = 0;
    int exist_ok = 0;
    static char *kwlist[] = {"parents", "exist_ok", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|pp", kwlist, &parents, &exist_ok))
        return NULL;

    PyObject *path_str = PureFastPath_str((PureFastPathObject *)self);
    if (path_str == NULL)
        return NULL;

    PyObject *os_module = PyImport_ImportModule("os");
    if (os_module == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *makedirs = PyObject_GetAttrString(os_module, "makedirs");
    Py_DECREF(os_module);
    if (makedirs == NULL) {
        Py_DECREF(path_str);
        return NULL;
    }

    PyObject *mk_args = Py_BuildValue("(O)", path_str);
    PyObject *mk_kwargs = Py_BuildValue("{s:O}", "exist_ok", exist_ok ? Py_True : Py_False);
    PyObject *result = PyObject_Call(makedirs, mk_args, mk_kwargs);
    Py_DECREF(makedirs);
    Py_DECREF(mk_args);
    Py_DECREF(mk_kwargs);
    Py_DECREF(path_str);

    if (result == NULL)
        return NULL;

    Py_DECREF(result);
    Py_RETURN_NONE;
}

static PyMethodDef FastPath_methods[] = {
    {"exists", (PyCFunction)FastPath_exists, METH_NOARGS,
     "Check if path exists"},
    {"is_file", (PyCFunction)FastPath_is_file, METH_NOARGS,
     "Check if path is a file"},
    {"is_dir", (PyCFunction)FastPath_is_dir, METH_NOARGS,
     "Check if path is a directory"},
    {"read_text", (PyCFunction)FastPath_read_text, METH_VARARGS | METH_KEYWORDS,
     "Read text from file"},
    {"write_text", (PyCFunction)FastPath_write_text, METH_VARARGS | METH_KEYWORDS,
     "Write text to file"},
    {"mkdir", (PyCFunction)FastPath_mkdir, METH_VARARGS | METH_KEYWORDS,
     "Create directory"},
    {NULL}  /* Sentinel */
};

static PyTypeObject FastPathType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "fastpath._path_c.FastPath",
    .tp_doc = "Fast path implementation with filesystem operations",
    .tp_basicsize = sizeof(FastPathObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_base = &PureFastPathType,  /* Inherit from PureFastPath */
    .tp_methods = FastPath_methods,
};

/* ========================================================================
 * Module initialization
 * ======================================================================== */

static PyModuleDef pathmodule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_path_c",
    .m_doc = "C implementation of fast path classes",
    .m_size = -1,
};

PyMODINIT_FUNC
PyInit__path_c(void)
{
    PyObject *m;

    /* Import allocator module */
    allocator_module = PyImport_ImportModule("fastpath._allocator_c");
    if (allocator_module == NULL)
        return NULL;

    PathAllocator_Type = PyObject_GetAttrString(allocator_module, "PathAllocator");
    if (PathAllocator_Type == NULL) {
        Py_DECREF(allocator_module);
        return NULL;
    }

    if (PyType_Ready(&PureFastPathType) < 0) {
        Py_DECREF(allocator_module);
        Py_DECREF(PathAllocator_Type);
        return NULL;
    }

    if (PyType_Ready(&FastPathType) < 0) {
        Py_DECREF(allocator_module);
        Py_DECREF(PathAllocator_Type);
        return NULL;
    }

    m = PyModule_Create(&pathmodule);
    if (m == NULL) {
        Py_DECREF(allocator_module);
        Py_DECREF(PathAllocator_Type);
        return NULL;
    }

    Py_INCREF(&PureFastPathType);
    if (PyModule_AddObject(m, "PureFastPath", (PyObject *)&PureFastPathType) < 0) {
        Py_DECREF(&PureFastPathType);
        Py_DECREF(m);
        Py_DECREF(allocator_module);
        Py_DECREF(PathAllocator_Type);
        return NULL;
    }

    Py_INCREF(&FastPathType);
    if (PyModule_AddObject(m, "FastPath", (PyObject *)&FastPathType) < 0) {
        Py_DECREF(&FastPathType);
        Py_DECREF(&PureFastPathType);
        Py_DECREF(m);
        Py_DECREF(allocator_module);
        Py_DECREF(PathAllocator_Type);
        return NULL;
    }

    return m;
}