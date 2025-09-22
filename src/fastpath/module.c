#include "fastpath.h"

/* Module definition */
static PyModuleDef fastpathmodule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "fastpath",
    .m_doc = "Fast path implementation with shared allocator",
    .m_size = -1,
};

PyMODINIT_FUNC
PyInit_fastpath(void)
{
    PyObject *m;

    /* Initialize types */
    if (PyType_Ready(&StringPoolType) < 0)
        return NULL;

    if (PyType_Ready(&TreeAllocatorType) < 0)
        return NULL;

    if (PyType_Ready(&PathAllocatorType) < 0)
        return NULL;

    if (PyType_Ready(&PureFastPathType) < 0)
        return NULL;

    if (PyType_Ready(&FastPathType) < 0)
        return NULL;

    /* Create module */
    m = PyModule_Create(&fastpathmodule);
    if (m == NULL)
        return NULL;

    /* Add types to module */
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

    Py_INCREF(&PureFastPathType);
    if (PyModule_AddObject(m, "PureFastPath", (PyObject *)&PureFastPathType) < 0) {
        Py_DECREF(&PureFastPathType);
        Py_DECREF(m);
        return NULL;
    }

    Py_INCREF(&FastPathType);
    if (PyModule_AddObject(m, "FastPath", (PyObject *)&FastPathType) < 0) {
        Py_DECREF(&FastPathType);
        Py_DECREF(&PureFastPathType);
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