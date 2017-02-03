# -*- coding: utf-8 -*-
"""
"""
import os

from nuka.task import Task
from nuka.tasks import http


class untar(Task):

    def __init__(self, src=None, dst=None, **kwargs):
        kwargs.setdefault('name', src)
        super(untar, self).__init__(src=src, dst=dst, **kwargs)

    def do(self):
        remove = False
        src = self.args['src']
        if src.startswith('http'):
            remove = True
            res = self.check(http.fetch(src=src).do())
            src = res['dst']
        res = self.sh(['tar', '-C', self.args['dst'], '-xzf', src])
        if remove:
            os.unlink(src)
        return res
