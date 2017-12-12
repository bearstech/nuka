# -*- coding: utf-8 -*-
from nuka.tasks import service
from nuka.tasks import apt
import pytest
import os


pytestmark = [
    pytest.mark.skipif(
        'centos' in os.environ['ENV_NAME'], reason='exclude centos'),
]


@pytest.mark.asyncio
async def test_01_install_services(host):
    await apt.install(['rsync'])


@pytest.mark.asyncio
async def test_start_doc(host):
    await service.start('rsync')


@pytest.mark.asyncio
async def test_restart_doc(host):
    await service.restart('rsync')


@pytest.mark.asyncio
async def test_stop_doc(host):
    await service.stop('rsync')


@pytest.mark.asyncio
async def test_service(host):
    assert await service.stop('rsync')
    assert await service.stop('rsync')
    assert await service.restart('rsync')
    assert await service.start('rsync')
    assert await service.stop('rsync')
    assert await service.start('rsync')
    assert await service.restart('rsync')


@pytest.mark.asyncio
async def test_service_diff(host, diff_mode):
    assert await service.stop('rsync')
    assert await service.start('rsync')
