# -*- coding: utf-8 -*-
from nuka.tasks import apt
import pytest
import os

pytestmark = [
    pytest.mark.skipif(
        'centos' in os.environ['ENV_NAME'], reason='exclude centos'),
]


@pytest.mark.asyncio
async def test_source_doc(host):
    res = await apt.source(
        name='url',
        key='https://deb.bearstech.com/bearstech-archive.gpg',
        src='deb http://deb.bearstech.com/debian jessie-bearstech main',
    )
    assert bool(res)


@pytest.mark.asyncio
async def test_debconf_set_selections_doc(host):
    res = await apt.debconf_set_selections(
        [('adduser', 'adduser/homedir-permission', 'true')]
    )
    assert bool(res)


@pytest.mark.asyncio
async def test_update_doc(host):
    res = await apt.update(cache=3600)
    assert bool(res)


@pytest.mark.asyncio
async def test_install_doc(host):
    res = await apt.install(['python'])
    assert bool(res)


@pytest.mark.asyncio
async def test_install_diff(host, diff_mode):
    with diff_mode:
        res = await apt.install(packages=['moreutils'])
        assert res.rc == 0
        assert '+moreutils\n' in res.res['diff'], res.res['diff']
