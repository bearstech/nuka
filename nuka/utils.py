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
    import zlib
except ImportError:
    zlib = None

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

try:
    import importlib
except ImportError:
    importlib = None  # NOQA


LOG = 60
logging.addLevelName(LOG, 'LOG')
CHANGED = logging.WARNING + 1
logging.addLevelName(CHANGED, 'CHANGED')
PROGRESS = logging.WARNING + 2
logging.addLevelName(PROGRESS, 'PROGRESS')


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


def import_module(name):
    if importlib is not None:
        return importlib.import_module(name)
    return __import__(name, globals(), locals(), [''])


def makedirs(dirname, mod=None, own=None):
    """create directories. return ``{'changed': True|False}``"""
    changed = False
    fut = ''
    dirname = dirname.rstrip('/')
    for p in dirname.split('/'):
        fut += p + '/'
        if not os.path.isdir(fut):
            os.makedirs(fut)
            changed = True
            if mod:
                chmod(fut, mod)
            if own:
                chown(fut, own)
    return dict(changed=changed)


def chmod(dst, mod, recursive=False):
    """chmod using command line"""
    if not os.path.exists(dst):
        raise OSError('{0} does not exist'.format(dst))
    if isinstance(mod, int):
        if recursive:
            raise RuntimeError()
        os.chmod(dst, mod)
    else:
        cmd = ['chmod']
        if recursive:
            cmd.append('-R')
        if isinstance(mod, (list, tuple)):
            mod = '{0}:{1}'.format(*mod)
        cmd.extend([mod, dst])
        subprocess.check_call(cmd,
                              stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)


def chown(dst, own, recursive=False):
    """chown using command line"""
    if not os.path.exists(dst):
        raise OSError('{0} does not exist'.format(dst))
    cmd = ['chown']
    if recursive:
        cmd.append('-R')
    if isinstance(own, (list, tuple)):
        own = '{0}:{1}'.format(*own)
    cmd.extend([own, dst])
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
        self.valids = [n for n in valids if n not in (34, 35, 39, 61, 92)]
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


def proto_dumps(data, content_type=u'plain'):
    """json.dumps() with headers. py2/3 compat"""
    data = json.dumps(data)
    if not isinstance(data, bytes):
        data = data.encode('utf8')
    if content_type == u'zlib':
        if zlib is not None:
            data = zlib.compress(data)
        else:
            content_type = u'plain'
    headers = (
        u'Content-type: {0}\nContent-Length: {1}\n'
    ).format(content_type, len(data)).encode('utf8')
    return headers + data


def proto_dumps_std(data, std, content_type='plain'):
    """json.dumps() to std with headers. py2/3 compat"""
    data = proto_dumps(data, content_type=content_type)
    std = getattr(std, 'buffer', std)
    std.write(data)


def proto_dumps_std_threadsafe(data, std):
    _write_lock.acquire()
    content_type = zlib is None and u'plain' or u'zlib'
    try:
        proto_dumps_std(data, std, content_type=content_type)
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
    content_type = std.readline()
    if isinstance(content_type, bytes):
        content_type = content_type.decode('utf8')
    try:
        content_type = content_type.split(':')[1].strip()
    except IndexError:
        raise ValueError(content_type)
    content_length = std.readline()
    if isinstance(content_length, bytes):
        content_length = content_length.decode('utf8')
    try:
        content_length = int(content_length.split(':')[1].strip())
    except IndexError:
        raise ValueError(content_length)
    data = std.read(content_length)
    if content_type == 'zlib':
        data = zlib.decompress(data)
    if isinstance(data, bytes):
        data = data.decode('utf8')
    try:
        data = json.loads(data)
    except ValueError:
        raise ValueError(data)
    return data
