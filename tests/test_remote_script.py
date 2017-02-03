# -*- coding: utf-8 -*-
import os
import sys
import pytest
import subprocess

import nuka
from nuka import utils
from nuka import config
from nuka.remote.task import Task


class command(Task):

    def do(self):
        return self.sh(self.args['cmd'])


script = os.path.join(
    os.path.dirname(nuka.__file__),
    'remote', 'script.py')


@pytest.fixture
def script_process(request):
    def _script_process(*args):
        p = subprocess.Popen(
            [sys.executable, script] + list(args),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return p
    return _script_process


@pytest.fixture
def remote_stdin(request):
    def _remote_stdin(**kwargs):
        cmd = kwargs.pop('cmd', ['echo', 'bear'])
        stdin = dict(
            task=('tests.test_remote_script', 'command'),
            remote_tmp=config['remote_tmp'],
            switch_user=None,
            args={'cmd': cmd, 'name': ''},
            check_mode=False,
            diff_mode=False,
            log_level=config['log']['levels']['remote_level'])
        stdin.update(kwargs)
        std = utils.io.BytesIO()
        utils.proto_dumps_std(stdin, std)
        std.seek(0)
        return std.read()
    yield _remote_stdin


def test_simple_script(script_process, remote_stdin):
    p = script_process()
    data = remote_stdin()
    stdout, stderr = p.communicate(data)
    assert not stderr
    data = utils.proto_loads_std(stdout)
    assert data['rc'] == 0


def test_kill_script(script_process, remote_stdin):
    p = script_process()
    data = remote_stdin(cmd=['sleep', '5'])
    data += utils.proto_dumps(dict(signal='SIGINT'))
    stdout, stderr = p.communicate(data)
    assert p.returncode == 0
    assert not stderr
    assert stdout
    data = utils.proto_loads_std(stdout)
    assert data['rc'] == 1, data
    assert data['signal'] == 'SIGINT'
