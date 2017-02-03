# -*- coding: utf-8 -*-
import importlib

_modules = (
    'zlib', 'psutils',
    'virtualenv', 'pip', 'setuptools',
    'requests',
    'lxml',
)


def update_inventory(inventory, modules=_modules):
    libs = inventory.setdefault('python_libs', {})
    for name in modules:
        try:
            importlib.import_module(name)
        except ImportError:
            libs[name] = False
        else:
            libs[name] = True
