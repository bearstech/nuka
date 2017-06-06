# -*- coding: utf-8 -*-
import sys


def update_inventory(inventory):
    try:
        import zlib  # NOQA
        zlib_avalaible = True
    except ImportError:  # pragma: no cover
        zlib_avalaible = False
    data = {
        'executable': sys.executable,
        'python_version': list(sys.version_info),
        'zlib_available': zlib_avalaible,
    }
    inventory['python'] = data
