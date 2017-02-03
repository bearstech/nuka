# -*- coding: utf-8 -*-
from nuka.tasks import shell
import pytest


@pytest.mark.asyncio
async def test_sh(host):
    assert (await shell.shell('ls / | grep etc'))


@pytest.mark.asyncio
async def test_command(host):
    assert (await shell.command(['ls', '/']))


@pytest.mark.asyncio
async def test_commands(host):
    assert (await shell.commands([['ls', '/']]))
