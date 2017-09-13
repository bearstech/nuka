# -*- coding: utf-8 -*-
import asyncio
import pytest
from nuka.hosts import base


def test_basehost():
    host = base.BaseHost(address='127.0.0.1')
    assert host.hostname == '127.0.0.1'
    assert host.bootstrap_command is None

    host = base.BaseHost(address='127.0.0.1', bootstrap_command='ls')
    assert host.bootstrap_command == 'ls'

    assert len(host.running_tasks()) == 0


def test_host():
    host = base.Host(hostname='localhost')
    assert 'ls' in host.wraps_command_line('ls')[-1]

    assert 'su' in host.wraps_command_line('ls', switch_user='user')[-1]
    host.use_sudo = True
    assert 'sudo' in host.wraps_command_line('ls', switch_user='user')[-1]
    assert 'sudo' in host.wraps_command_line('ls', switch_user='root')[-1]

    assert 'user' in host.wraps_command_line('ls',
                                             switch_ssh_user='user')


def test_localhost():
    host = base.LocalHost()
    assert host.wraps_command_line('ls') == ['bash', '-c', 'ls']


@pytest.mark.asyncio
async def test_host_session(host):
    loop = host.loop
    host = base.BaseHost(hostname='localhost')
    host.loop = loop

    assert len(host._sessions) == 0
    await host.acquire_session_slot()
    assert len(host._sessions) == 1
    host.free_session_slot()
    assert len(host._sessions) == 0


@pytest.mark.asyncio
async def test_host_cancelled(host):
    host.cancel()
    with pytest.raises(asyncio.CancelledError):
        await host.run_command('ls')


@pytest.mark.asyncio
async def test_run_command(host, wait):
    res = await host.run_command('ls /')
    assert b'etc\n' in res['stdout']

    res = await host.run_command('cat -', stdin=b'echo', close_stdin=True)
    assert b'echo' in res['stdout']

    res = await host.run_command('ls /nope')
    assert res['rc'] == 2
