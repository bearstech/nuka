# -*- coding: utf-8 -*-
"""
unix user related tasks
"""
import os
from nuka import utils
from nuka.task import Task
from nuka.tasks import file


class delete_user(Task):
    """remove a unix account"""

    def __init__(self, username=None, **kwargs):
        kwargs.setdefault('name', username)
        super(delete_user, self).__init__(username=username, **kwargs)

    def do(self):
        username = self.args['username']
        if not self.sh(['id', username], check=False)['rc']:
            return self.sh(['userdel', '-r', username])
        return dict(rc=0, username=username)

    def diff(self):
        username = self.args['username']
        diff = ''
        if not self.sh(['id', username], check=False)['rc']:
            diff = self.texts_diff(username, '')
        return dict(rc=0, diff=diff, username=username)


class create_user(Task):
    """create a unix account"""

    home_format = '/home/{0}'
    gecos_format = 'user {0}'

    def __init__(self, username=None, **kwargs):
        kwargs.setdefault('name', username)
        kwargs.setdefault('gecos', self.gecos_format.format(username))
        kwargs.setdefault('home', self.home_format.format(username))
        super(create_user, self).__init__(username=username, **kwargs)

    def do(self):
        username = self.args['username']
        home = self.args['home']
        gecos = self.args['gecos']
        if self.sh(['id', username], check=False)['rc']:
            if self.is_debian:
                # ensure adduser is installed (wheezy do not have it)
                res = self.sh(['which', 'adduser'], check=False)
                if res['rc'] != 0:  # pragma: no cover
                    raise OSError('adduser is not available')
                cmd = [
                    'adduser', '--quiet', '--disabled-password',
                    '--gecos', gecos, '--home', home, username]
            else:
                cmd = [
                    'useradd',  '-p', '\*', '-c', gecos,
                    '-m',  '--home-dir', home, username]
            res = self.sh(cmd)
        else:
            res = dict(rc=0, changed=False)
        res.update(username=username, home=home)
        return res

    def diff(self):
        username = self.args['username']
        home = self.args['home']
        diff = ''
        if self.sh(['id', username], check=False)['rc'] != 0:
            diff = self.texts_diff('', username)
        if not os.path.isdir(home):
            diff += self.texts_diff('', home)
        res = dict(rc=0, diff=diff, **self.args)
        res.update(username=username, home=self.args['home'])
        return res


class create_www_user(create_user):
    """create a unix account with /var/www/{username} as home"""

    home_format = '/var/www/{0}'
    gecos_format = 'www user {0}'


class authorized_keys(file.put):
    """upload ssh keys from string or file"""

    def __init__(self, username=None, keys=None, keysfile=None, **kwargs):
        kwargs.update(name=username, username=username, switch_user=username)
        if 'files' not in kwargs:
            dst = '~/.ssh/authorized_keys'
            if keysfile:
                kwargs['files'] = [dict(src=keysfile, dst=dst, mod='644')]
            elif keys:
                kwargs['files'] = [dict(data=keys, dst=dst, mod='644')]
            else:
                raise RuntimeError('You must provide keys or keysfile')
        super(authorized_keys, self).__init__(**kwargs)

    def do(self):
        utils.makedirs(os.path.expanduser('~/.ssh'), mod='700')
        super(authorized_keys, self).do()
