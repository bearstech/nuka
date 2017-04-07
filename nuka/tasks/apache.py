# -*- coding: utf-8 -*-
"""
apache related tasks
"""
import os
from nuka.task import Task


class a2ensite(Task):
    """a2ensite"""

    def __init__(self, names=None, **kwargs):
        super(a2ensite, self).__init__(names=names, **kwargs)

    def pre_process(self):
        args = self.args
        class_name = self.__class__.__name__
        if class_name.startswith('a2en'):
            enable = True
            type = class_name[4:]
        else:
            enable = False
            type = class_name[5:]
        type = type if type == 'conf' else type + 's'
        args.update(
            binary=class_name,
            enable=enable,
            type=type,
        )
        elements = []
        names = args['names']
        if isinstance(names, str):
            names = [names]
        for name in names:
            args['name'] = name
            filename = (
                '/etc/apache2/{type}-enabled/{name}'.format(**args))
            if type == 'mods':
                filename += '.load'
            elif type == 'conf':
                filename += '.conf'
            elements.append((name, filename))
        args.update(name=', '.join(names), elements=elements)

    def do(self):
        diffs = self.get_diffs()
        if diffs:
            return self.sh([self.args['binary']] + diffs)
        else:
            return dict(rc=0, changed=False)

    def get_diffs(self):
        diffs = []
        for name, filename in self.args['elements']:
            if self.args['enable']:
                if not os.path.isfile(filename):
                    diffs.append(name)
            elif os.path.isfile(filename):
                    diffs.append(name)
        return diffs

    def diff(self):
        diffs = self.get_diffs()
        diffs = [n + '\n' for n in diffs]
        if self.args['enable']:
            diff = self.lists_diff([], diffs)
        else:
            diff = self.lists_diff(diffs, [])
        return dict(rc=0, diff=diff)


class a2dissite(a2ensite):
    """a2dissite"""


class a2enmod(a2ensite):
    """a2enmod"""


class a2dismod(a2ensite):
    """a2dismod"""


class a2enconf(a2ensite):
    """a2enconf"""


class a2disconf(a2ensite):
    """a2disconf"""
