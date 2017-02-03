# -*- coding: utf-8 -*-
from nuka.remote.task import Task


def test_remote_task():
    p = Task.from_dict(dict(name='yo', args={}))

    res = p.sh(['ls'], env=dict(K='V'))
    assert res['rc'] == 0
    assert len(res['stdout'])
    assert not len(res['stderr'])

    res = p.sh(['ls', '/nope'], env=dict(K='V'), check=False)
    assert res['rc'] == 2
    assert not len(res['stdout'])
    assert len(res['stderr'])

    res = p.sh(['lsss', '/nope'], check=False)
    assert res['rc'] == 1
