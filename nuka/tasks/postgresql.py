# -*- coding: utf-8 -*-
from nuka.task import Task


class psql(Task):
    """psql"""

    diff = False

    def __init__(self, sql=None, **kwargs):
        kwargs.setdefault('switch_user', 'postgres')
        super(psql, self).__init__(sql=sql, **kwargs)

    def do(self):
        return self.sh(['psql', '-tAc', self.args['sql']])


class create_db(Task):
    """create a database and grant user"""

    def __init__(self, name=None, user=None, password=None, **kwargs):
        kwargs.setdefault('switch_user', 'postgres')
        kwargs.setdefault('template', 'template1')
        kwargs.setdefault('locale', 'en_US.UTF-8')
        super(create_db, self).__init__(name=name, user=user,
                                        password=password, **kwargs)

    def user_exists(self):
        s = "SELECT 1 FROM pg_roles WHERE rolname='{user}'".format(**self.args)
        res = self.sh(['psql', '-tAc', s], check=False)
        return res['stdout'].strip() == "1"

    def db_exists(self):
        res = self.sh(['psql', self.args['name'], '-c', ''], check=False)
        return res['rc'] == 0

    def do(self):
        if not self.db_exists():
            if not self.user_exists():
                s = "CREATE ROLE {user} WITH PASSWORD '{password}';"
                self.sh(['psql', '-tAc', s.format(**self.args)])
            return self.sh([
                'createdb',
                '--owner', self.args['user'],
                '--template', self.args['template'],
                '--lc-ctype', self.args['locale'],
                '--lc-collate', self.args['locale'],
                self.args['name'],
            ])
        else:
            return dict(rc=0, changed=False)

    def diff(self):
        diff = []
        if not self.user_exists():
            diff.append(self.texts_diff('', self.args['user'],
                                        tofile='role'))
        if not self.db_exists():
            diff.append(self.texts_diff('', self.args['name'],
                                        tofile='database'))
        if diff:
            return dict(diff='\n'.join(diff))
        return dict(rc=0, changed=False)
