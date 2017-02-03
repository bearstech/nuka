# -*- coding: utf-8 -*-
"""

nuka.utils.secret
========================

.. autoclass:: secret

nuka.utils.chmod
========================

.. autofunction:: chmod

nuka.utils.chown
========================

.. autofunction:: chown

nuka.utils.makedirs
========================

.. autofunction:: makedirs

"""
import io
import os
import sys
import time
import string
import logging
import threading
import subprocess

_write_lock = threading.Lock()

PY3 = sys.version_info[0] == 3

if not PY3:
    def next(o):
        return o.next()
_next = next


try:
    import ujson as json
except ImportError:
    import json  # NOQA

try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve  # NOQA

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO  # NOQA


def default_watcher(delay=5):
    def watcher(task, process):
        start = time.time()
        inc = delay
        while True:
            if task.is_alive(process):
                value = time.time() - start
                if value > inc:
                    inc += delay
                    task.send_progress(
                        'is running for {0}s'.format(int(value)),
                        level=logging.DEBUG)
                yield
            else:
                # process is dead
                yield
    return watcher


def makedirs(dirname, mod=None, own=None):
    """create directories. return ``{'changed': True|False}``"""
    changed = False
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
        changed = True
    if mod:
        chmod(dirname, mod)
    if own:
        chown(dirname, own)
    return dict(changed=changed)


def chmod(dst, mod):
    """chmod"""
    if not os.path.exists(dst):
        raise OSError('{0} does not exist'.format(dst))
    if isinstance(mod, int):
        os.chmod(dst, mod)
    else:
        if PY3:
            os.chmod(dst, eval('0o' + mod))
        else:
            os.chmod(dst, eval('0' + mod))


def chown(dst, own, recursive=False):
    """chown using command line"""
    if not os.path.exists(dst):
        raise OSError('{0} does not exist'.format(dst))
    cmd = ['chown']
    if recursive:
        cmd.append('-R')
    if isinstance(own, list, tuple):
        own = '{0}:{1}'.format(*own)
    cmd.append(own)
    subprocess.check_call(cmd,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)


def best_executable():
    executables = [
        '/usr/bin/python3.6',
        '/usr/bin/python3.5',
        '/usr/bin/python3.4',
        '/usr/bin/python2.7',
    ]
    for executable in executables:
        if os.path.isfile(executable):
            return executable
    return sys.executable


def isexecutable(path):
    return os.access(path, os.X_OK)


class secret(object):
    """secret word generation::

        >>> s = secret('something')
        >>> s.next()
        'F)>x|o;J7sOhWV~F'
        >>> s.next()
        'DP@:?|v%LaSB2v?b'

    You can use your own alphabet::

        >>> s = secret('something', alphabet='abc')
        >>> s.next()
        'bbbbcaaacacbbcbb'

    Or just ascii letters/digits::

        >>> s = secret('something', alphabet='ascii')
        >>> s.next()
        'FxoJ7sOhWVFYRN7v'

    You can also change the length::

        >>> s = secret('something', alphabet='ascii', length=3)
        >>> s.next()
        'Fxo'
    """

    def __init__(self, value, alphabet=None, length=16):
        self.value = value
        if alphabet == 'ascii':
            valids = [ord(a) for a in string.ascii_letters]
            valids += [ord(a) for a in string.digits]
        elif alphabet is None:
            valids = list(range(33, 127))
        else:
            valids = [ord(a) for a in alphabet]
        self.valids = [n for n in valids if n not in (34, 35, 39, 92)]
        self.length = length
        self.iterator = self.iterator()

    def iterator(self):
        import hashlib
        i = 0
        while True:
            pw = ''
            j = 0
            i += 1
            while len(pw) < self.length:
                j += 1
                v = '{0}-{1}-{2}'.format(self.value, i, j)
                h = hashlib.sha512(v.encode('utf8'))
                pw += ''.join(chr(c) for c in h.digest() if c in self.valids)
            yield pw[:self.length]

    def next(self):
        return next(self.iterator)


def proto_dumps(data):
    """json.dumps() with headers. py2/3 compat"""
    data = json.dumps(data)
    if not isinstance(data, bytes):
        data = data.encode('utf8')
    header = u'Content-Length: {0}\n'.format(len(data)).encode('utf8')
    return header + data


def proto_dumps_std(data, std):
    """json.dumps() to std with headers. py2/3 compat"""
    data = proto_dumps(data)
    std = getattr(std, 'buffer', std)
    std.write(data)


def proto_dumps_std_threadsafe(data, std):
    _write_lock.acquire()
    try:
        proto_dumps_std(data, std)
        std.flush()
    finally:
        _write_lock.release()


def proto_loads_std(std):
    """json.loads() from std with headers. py2/3 compat"""
    if isinstance(std, bytes):
        std = io.BytesIO(std)
        std.seek(0)
    else:
        std = getattr(std, 'buffer', std)
    header = std.readline()
    length = header.split(b': ')
    try:
        length = int(length[1].strip())
    except IndexError:
        raise ValueError(length)
    data = std.read(length)
    if isinstance(data, bytes):
        data = data.decode('utf8')
    try:
        data = json.loads(data)
    except ValueError:
        raise ValueError(data)
    return data
