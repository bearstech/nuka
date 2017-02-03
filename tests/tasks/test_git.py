# -*- coding: utf-8 -*-
from nuka.tasks import apt
from nuka.tasks import git
import pytest
import os

pytestmark = [
    pytest.mark.skipif(
        'debian' not in os.environ['ENV_NAME'], reason='debian only'),
]


@pytest.mark.asyncio
async def test_clone(host):
    assert (await apt.install(packages=['git']))
    # FIXME: branch sucks on wheezy. maybe because an old git version
    # res = await git.git(
    #     src='https://github.com/gawel/aiocron.git',
    #     dst='/tmp/nuka_clone',
    # )
    # assert res
    res = await git.git(
        src='https://github.com/gawel/aiocron.git',
        dst='/tmp/nuka_clone',
        tag='0.1',
    )
    res = await git.git(
        src='https://github.com/gawel/aiocron.git',
        dst='/tmp/nuka_clone',
        tag='0.6',
    )
    assert res
    with pytest.raises(RuntimeError):
        await git.git(
            src='https://github.com/gawel/aiocron.git',
            dst='/tmp/nuka_clone',
            tag='0.6', branch='master'
        )
