# -*- coding: utf-8 -*-
# Copyright 2017 by Bearstech <py@bearstech.com>
#
# This file is part of nuka.
#
# nuka is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# nuka is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with nuka. If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import signal
import logging
import tempfile

from nuka.task import Task
from nuka import utils


def main(data=None):

    if data is None:
        try:
            data = utils.proto_loads_std(Task.stdin)
        except Exception:
            res = dict(rc=1, exc=Task.format_exception())
            Task.exit(res)
        if 'environ' in data:
            os.environ.update(data['environ'])
        tempfile.tempdir = data['remote_tmp']

        logging.basicConfig(
            format='%(levelname)s:%(message)s',
            level=data.pop('log_level'),
            stream=Task.logfile)

    res = {}

    module, klass_name = data['task']

    try:
        mod = utils.import_module(module)
        task = getattr(mod, klass_name).from_dict(data)
    except Exception:
        res = dict(rc=1, exc=Task.format_exception())
        Task.exit(res)

    # clean exit on SIGINT
    signal.signal(signal.SIGALRM, task.on_alarm)
    signal.alarm(task.alarm_delay)

    if data['diff_mode']:
        meth_name = 'diff'
    else:
        meth_name = 'do'

    res = {}

    try:
        meth = getattr(task, meth_name)
    except AttributeError:
        res = dict(rc=0, stderr='{0} not supported'.format(meth_name))
        task.exit(res)

    try:
        res = meth() or {}
    except Exception:
        res = dict(rc=1, exc=task.format_exception())
    task.exit(res)


def setup():

    logging.basicConfig(
        format='%(levelname)s:%(message)s',
        level=logging.WARN,
        stream=Task.logfile)

    # check if we have a venv
    python = os.path.join(
        os.path.abspath(os.path.dirname(sys.argv[0])),
        'bin', 'python')
    same_dir = os.path.dirname(sys.executable) == os.path.dirname(python)
    if os.path.isfile(python) and not same_dir:
        os.execv(python, [python] + sys.argv)
    elif not os.path.isfile(python):
        # get best binary
        from nuka.utils import best_executable
        python = best_executable()
        if os.path.isfile(python) and sys.executable != python:
            os.execv(python, [python] + sys.argv)

    # launch setup task
    main(data=dict(
        task=('nuka.tasks.setup', 'setup'),
        args={},
        diff_mode=False,
        log_level=logging.WARNING)
    )


if __name__ == '__main__':
    if '--setup' in sys.argv:
        setup()
    else:
        main()
