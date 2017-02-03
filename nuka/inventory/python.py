# -*- coding: utf-8 -*-
import sys


def update_inventory(inventory):
    data = {
        'executable': sys.executable,
        'python_version': list(sys.version_info),
    }
    inventory['python'] = data
