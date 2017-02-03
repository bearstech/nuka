# -*- coding: utf-8 -*-
"""
python virtualenv
"""
import os
import sys
from nuka import utils
from nuka.tasks import file
from nuka.tasks import http

GET_PIP = 'https://bootstrap.pypa.io/get-pip.py'


def d():
    import logging
    with open('/tmp/nuka_provisionning/nuka/bin/coverage') as fd:
        logging.warn(fd.read())


class virtualenv(file.put):
    """create a python virtualenv"""

    def __init__(self, dst=None, requirements=None, upgrade=False, **kwargs):
        kwargs.setdefault('name', dst)
        kwargs.setdefault('requirements', requirements)
        super(virtualenv, self).__init__(dst=dst, **kwargs)

    def pre_process(self):
        if self.args['requirements']:
            self.args['files'] = [dict(
                src=self.args['requirements'],
                dst=os.path.join(self.args['dst'],
                                 os.path.basename(self.args['requirements'])))]
            super(virtualenv, self).pre_process()

    def do(self):
        dst = self.args['dst']
        pip = os.path.join(dst, 'bin', 'pip')
        binary = os.path.join(dst, 'bin', 'python')
        if not os.path.isfile(binary):
            executable = self.args.get('executable',
                                       utils.best_executable())
            if 'python3' in executable:
                # use stdlib venv
                args = [dst]
                self.sh([executable, '-m', 'venv', '--without-pip'] + args)
                self.sh([binary, '-m', 'ensurepip'], check=False)
            else:
                # use virtualenv
                dirname = os.path.dirname(sys.executable)
                venv = os.path.join(dirname, 'virtualenv')
                if not os.path.isfile(venv):
                    venv = 'virtualenv'

                res = self.sh([venv, '-p', executable, dst])

        if not os.path.isfile(binary):
            raise OSError('Not able to create {0}'.format(binary))

        has_pip = False
        if os.path.isfile(pip):
            has_pip = True
        if not has_pip:
            res = self.sh([binary, '-m', 'pip', '--version'], check=False)
            if res['rc'] == 0:
                has_pip = True

        if not has_pip:
            res = self.check(http.fetch(
                src=GET_PIP,
                dst=os.path.join(dst, 'get-pip.py')).do())
            res = self.sh([binary, res['dst']])
        else:
            res = dict(rc=0)

        files = self.args.get('files') or []
        if files:
            self.check(super(virtualenv, self).do())
            for f in files:
                if os.path.isfile(pip):
                    cmd = [pip, 'install']
                else:
                    cmd = [binary, '-m', 'pip', 'install']
                if self.args.get('upgrade'):
                    cmd.append('--upgrade')
                cmd.extend(['-r', f['dst']])
                self.sh(cmd)
        res.update(python=binary)
        return res

    def diff(self):
        dst = self.args['dst']
        binary = os.path.join(dst, 'bin', 'python')
        diff = ''
        if not os.path.isfile(binary):
            diff += self.texts_diff('', binary, fromfile=dst)
        res = super(virtualenv, self).diff()
        diff += res.get('diff', '')
        return dict(rc=0, diff=diff, python=binary)
