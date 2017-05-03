# -*- coding: utf-8 -*-
"""
services related tasks
"""
from nuka.task import Task


class start(Task):
    """ensure a service is started"""

    def __init__(self, name=None, **kwargs):
        super(start, self).__init__(name=name, **kwargs)

    def do(self):
        res = self.sh(['service', self.args['name'], 'status'], check=False)
        if res['rc'] != 0:
            res = self.sh(['service', self.args['name'], 'start'])
        else:
            res['changed'] = False
        return res

    def diff(self):
        res = self.sh(['service', self.args['name'], 'status'], check=False)
        diff = ''
        if res['rc'] != 0:
            diff = self.texts_diff('', self.args['name'])
        return dict(diff=diff)


class restart(Task):
    """restart one or more service"""

    diff = False

    def __init__(self, services=None, **kwargs):
        if isinstance(services, str):
            services = [services]
        kwargs.update(
            name=', '.join(services),
            services=services)
        super(restart, self).__init__(**kwargs)

    def do(self):
        for service in self.args['services']:
            res = self.sh(['service', service, 'restart'])
        return res


class reload(Task):
    """reload one or more service"""

    diff = False

    def __init__(self, services=None, **kwargs):
        if isinstance(services, str):
            services = [services]
        kwargs.update(
            name=', '.join(services),
            services=services)
        super(reload, self).__init__(**kwargs)

    def do(self):
        for service in self.args['services']:
            res = self.sh(['service', service, 'reload'])
        return res


class stop(Task):
    """ensure a service is stoped"""

    def __init__(self, name=None, **kwargs):
        super(stop, self).__init__(name=name, **kwargs)

    def do(self):
        return self.sh(['service', self.args['name'], 'stop'])

    def diff(self):
        res = self.sh(['service', self.args['name'], 'status'], check=False)
        if res['rc'] == 0:
            diff = self.lists_diff(['{0}\n'.format(self.args['name'])], [])
        else:
            diff = ''
        return dict(diff=diff)
