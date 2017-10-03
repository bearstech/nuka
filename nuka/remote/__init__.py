# -*- coding: utf-8 -*-
import tarfile
import time
import sys
import os
import io

import nuka


def exclude_pyc(info):
    if info.name.endswith(('.py', 'tasks', 'inventory')):
        return info


def build_archive(extra_classes=[], mode='x:gz'):
    """build a tarball with required scripts and python modules"""
    try:
        return build_archive.archives[mode]
    except KeyError:

        modules = nuka.config['inventory_modules'][:]
        modules.extend([klass.__module__ for klass in extra_classes])

        dirnames = set()
        filenames = set()
        for module in modules:
            if module.startswith('nuka.'):
                continue
            mod = sys.modules[module]
            mod_path = module.replace('.', '/') + '.py'
            filenames.add((mod.__file__, mod_path))
            dirname = mod_path
            while os.sep in dirname:
                dirname = os.path.dirname(mod_path)
                dirnames.add(dirname)

        nuka_dir = os.path.dirname(nuka.__file__)
        fd = io.BytesIO()
        with tarfile.open(fileobj=fd, mode=mode) as tfd:
            for dirname in dirnames:
                filename = dirname + '/__init__.py'
                if filename not in filenames:
                    tarinfo = tarfile.TarInfo(name=filename)
                    tarinfo.size = len(b'')
                    tarinfo.mtime = time.time()
                    tfd.addfile(tarinfo, io.BytesIO(b''))
            for src, dst in filenames:
                tfd.add(src, dst)
            tfd.add(os.path.join(nuka_dir, 'inventory'),
                    'nuka/inventory', filter=exclude_pyc)
            tfd.add(os.path.join(nuka_dir, 'tasks'),
                    'nuka/tasks', filter=exclude_pyc)
            tfd.add(os.path.join(nuka_dir, 'remote/task.py'),
                    'nuka/task.py')
            tarinfo = tarfile.TarInfo(name='nuka/__init__.py')
            tarinfo.size = len(b'')
            tarinfo.mtime = time.time()
            tfd.addfile(tarinfo, io.BytesIO(b''))
            tfd.add(os.path.join(nuka_dir, 'utils.py'),
                    'nuka/utils.py')
            tfd.add(os.path.join(nuka_dir, 'remote/script.py'),
                    'script.py')

            filenames = tfd.getnames()

        fd.seek(0)
        build_archive.archives[mode] = fd.read()

        if nuka.cli.args.verbose > 6:
            print('tarfile({0}ko): \n - {1}'.format(
                int(len(build_archive.archives[mode]) / 1024),
                '\n - '.join(filenames)))

        return build_archive.archives[mode]


build_archive.archives = {}
