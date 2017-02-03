# -*- coding: utf-8 -*-
"""
"""
import os
import tempfile
import posixpath
from nuka.task import Task


class fetch(Task):
    """fetch content from internet"""

    def __init__(self, src=None, dst=None, **kwargs):
        kwargs.setdefault('name', src)
        super(fetch, self).__init__(src=src, dst=dst, **kwargs)

    def fetch(self, dst, src):
        if os.path.isfile('/usr/bin/curl'):
            res = self.sh(['curl', '-so', dst, src])
        elif os.path.isfile('/usr/bin/wget'):
            res = self.sh(['wget', '-qO', dst, src])
        else:
            from nuka.utils import urlretrieve
            urlretrieve(src, dst)
            res = {'rc': 0}
        return res

    def do(self):
        src = self.args['src']
        dst = self.args['dst']
        if dst is None:
            filename = posixpath.split(src.strip('/'))[-1]
            if not filename:
                with tempfile.NamedTemporaryFile(prefix='http_fetch_') as fd:
                    dst = fd.name
            else:
                dst = os.path.join(tempfile.gettempdir(), filename)
        res = self.fetch(dst, src)
        res.update(dst=dst)
        return res
