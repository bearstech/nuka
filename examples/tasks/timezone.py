# -*- coding: utf-8 -*-
import codecs
from nuka.task import Task


class timezone(Task):

    def __init__(self, tz=None, **kwargs):
        # ensure we have a name to get a better repr() in logs
        kwargs.setdefault('name', tz)
        super(timezone, self).__init__(tz=tz, **kwargs)

    def do(self):
        """do the job: change the timezone file if needed"""
        tz = self.args['tz']
        changed = False
        with codecs.open('/etc/timezone', 'r', 'utf8') as fd:
            current_tz = fd.read().strip()
        if current_tz != tz:
            changed = True
            with codecs.open('/etc/timezone', 'w', 'utf8') as fd:
                current_tz = fd.write(tz + '\n')
        # we must return a dictionary with at least a return code and
        # the change state
        return dict(rc=0, changed=changed)

    def diff(self):
        """generate diff between actual state and task value.
        Implementing this method is not required but recommended"""
        tz = self.args['tz']
        with codecs.open('/etc/timezone', 'r', 'utf8') as fd:
            current_tz = fd.read().strip()
        diff = ''
        if current_tz != tz:
            diff = self.text_diff(current_tz, tz)
        return dict(diff=diff)
