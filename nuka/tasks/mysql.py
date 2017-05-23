# -*- coding: utf-8 -*-
"""
mysql related tasks
"""
import os
import codecs
import getpass

from nuka import utils
from nuka.task import Task


class my_cnf(Task):
    """create ~/.my.cnf"""

    def __init__(self, password=None, switch_user='root', **kwargs):
        kwargs['name'] = '~{0}/.my.cnf'.format(switch_user)
        super(my_cnf, self).__init__(switch_user=switch_user,
                                     password=password, **kwargs)

    def do(self):
        self.args['user'] = getpass.getuser()
        dst = os.path.expanduser('~/.my.cnf')
        old_data = ''
        if os.path.isfile(dst):
            with codecs.open(dst, 'r', 'utf8') as fd:
                old_data = fd.read()
        data = (
            '[client]\n'
            'user={user}\n'
            'password={password}\n').format(**self.args)
        changed = old_data != data
        if changed:
            with codecs.open(dst, 'w', 'utf8') as fd:
                fd.write(data)
            utils.chmod(dst, '600')
        self.args.pop('password')
        return dict(rc=0, changed=changed, dst=dst)

    def diff(self):
        self.args['user'] = getpass.getuser()
        dst = os.path.expanduser('~/.my.cnf')
        old_data = ''
        if os.path.isfile(dst):
            with codecs.open(dst, 'r', 'utf8') as fd:
                old_data = fd.read()
        data = (
            '[client]\n'
            'user={user}\n'
            'password={password}\n').format(**self.args)
        diff = self.texts_diff(old_data, data, fromfile=dst)
        return dict(rc=0, diff=diff)


class set_root_password(my_cnf):
    """set mysql root password and store it in ~/.my.cnf"""

    def __init__(self, password=None, **kwargs):
        kwargs.update(password=password, switch_user='root')
        super(set_root_password, self).__init__(**kwargs)

    def do(self):
        new_password = self.args['password']
        old_password = None

        # get old password
        dst = os.path.expanduser('/root/.my.cnf')
        if os.path.isfile(dst):
            with codecs.open(dst, 'r', 'utf8') as fd:
                for line in fd:
                    line = line.strip()
                    if line.startswith('password'):
                        old_password = line.split('=')[1].strip()

        if old_password != new_password:
            # change password
            cmd = ['mysqladmin', 'password', new_password]
            if old_password:
                cmd[1:1] = ['--password=' + old_password]
            self.sh(cmd)
        # forward to my_cnf to update /root/.my.cnf
        return super(set_root_password, self).do()


class create_db(Task):
    """create a database and grant user"""

    statement = '''
    CREATE DATABASE IF NOT EXISTS {name};
    GRANT ALL PRIVILEGES ON *.* TO '{user}'@'%' IDENTIFIED BY '{password}';
    FLUSH PRIVILEGES;
    '''

    def __init__(self, name=None, user=None, password=None, **kwargs):
        super(create_db, self).__init__(name=name, user=user,
                                        password=password, **kwargs)

    def do(self):
        return self.sh('mysql', stdin=self.statement.format(**self.args))


class execute(Task):
    """execute a sql statement"""

    diff = False

    def __init__(self, sql=None, **kwargs):
        kwargs.setdefault('name', sql)
        super(execute, self).__init__(sql=sql, **kwargs)

    def do(self):
        return self.sh('mysql', stdin=self.args['sql'])
