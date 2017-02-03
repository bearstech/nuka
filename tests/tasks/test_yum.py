# -*- coding: utf-8 -*-
from nuka.tasks import yum
import pytest
import os

pytestmark = [
    pytest.mark.skipif(
        'centos' not in os.environ['ENV_NAME'], reason='centos only'),
]


@pytest.mark.asyncio
async def test_update_doc(host):
    res = await yum.update(cache=3600)
    assert bool(res)


@pytest.mark.asyncio
async def test_install_doc(host):
    res = await yum.install(['python'])
    assert bool(res)


@pytest.mark.asyncio
async def test_install_diff(host, diff_mode):
    with diff_mode:
        res = await yum.install(packages=['moreutils'])
        assert res.rc == 0
        assert '+moreutils\n' in res.res['diff'], res.res['diff']

        res = await yum.install(packages=['python'])
        assert res.rc == 0
        assert '+python\n' not in res.res['diff'], res.res['diff']
