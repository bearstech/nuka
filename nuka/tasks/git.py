# -*- coding: utf-8 -*-
"""
git related tasks
"""
import os
import logging as log
from nuka.task import Task


class git(Task):
    """git clone/fetch"""

    def __init__(self, src=None, dst=None,
                 branch=None, tag=None, **kwargs):
        kwargs.setdefault('name', src)
        kwargs.update(src=src, dst=dst, branch=branch, tag=tag)
        super(git, self).__init__(**kwargs)

    def pre_process(self):
        if self.args['branch'] and self.args['tag']:
            raise RuntimeError('Do not use both tag and branch')
        if self.args['branch'] is None and self.args['tag'] is None:
            self.args['branch'] = 'master'
        if self.args['tag']:
            self.args['depth'] = 1

    def current_ref(self):
        ref = self.sh(['git', 'rev-parse', 'HEAD'], check=False)
        if ref['rc'] == 0:
            ref = ref['stdout'].strip()
            return ref

    def do(self):
        src = self.args['src']
        dst = self.args['dst']
        branch = self.args['branch']
        tag = self.args['tag']
        ref = branch or tag
        cmd = ['git']
        if os.path.isdir(dst):
            old_ref = self.current_ref()
            os.chdir(dst)
            cmd.append('fetch')
            if tag:
                cmd.append('--depth=1')
            cmd.extend([src, ref])
        else:
            old_ref = None
            cmd += ['clone']
            if tag:
                cmd.extend([
                    '--depth=1', '--single-branch',
                    '-b', tag, '--depth=1'])
            cmd.extend([src, dst])
        log.info(cmd)
        self.sh(cmd)
        os.chdir(dst)
        if tag:
            self.sh(['git',  'fetch', '--tags'])
        res = self.sh(['git', 'checkout',  ref])
        res['changed'] = old_ref != self.current_ref()
        return res
