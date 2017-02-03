# -*- coding: utf-8 -*-
"""
command line related tasks
"""
from nuka import utils
from nuka.task import Task


class commands(Task):
    """run multiple command"""

    def __init__(self, cmds=None, **kwargs):
        kwargs.setdefault('name', cmds)
        super(commands, self).__init__(cmds=cmds, **kwargs)

    def do(self):
        for cmd in self.args['cmds']:
            kwargs = {}
            watch = self.args.get('watch')
            if watch:  # pragma: no cover
                kwargs['watcher'] = utils.default_watcher(delay=watch)
            res = self.sh(cmd, **kwargs)
        res.pop('stderr')
        return res


class command(Task):
    """run a task"""

    def __init__(self, cmd=None, **kwargs):
        kwargs.setdefault('name', cmd)
        super(command, self).__init__(cmd=cmd, **kwargs)

    def do(self):
        kwargs = {}
        watch = self.args.get('watch')
        if watch:  # pragma: no cover
            kwargs['watcher'] = utils.default_watcher(delay=watch)
        res = self.sh(self.args['cmd'], **kwargs)
        res.pop('stderr')
        return res


class shell(Task):
    """run a shell line (allow pipes)"""

    def __init__(self, cmd=None, **kwargs):
        kwargs.setdefault('name', cmd)
        super(shell, self).__init__(cmd=cmd, **kwargs)

    def do(self):
        kwargs = {'shell': True}
        watch = self.args.get('watch')
        if watch:  # pragma: no cover
            kwargs['watcher'] = utils.default_watcher(delay=watch)
        cmd = self.args['cmd']
        if isinstance(cmd, list):
            cmd = ' '.join(cmd)
        res = self.sh(cmd, **kwargs)
        res.pop('stderr')
        return res
