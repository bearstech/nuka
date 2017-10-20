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

from asyncio import subprocess
from asyncio import streams
import asyncio
import random
import socket
import time
import zlib
import os

import asyncssh
import asyncssh.misc

import nuka
from nuka import utils

DEFAULT_LIMIT = streams._DEFAULT_LIMIT

asyncssh_connections = {}
asyncssh_connections_tasks = {}
asyncssh_keypairs = []
asyncssh_known_hosts = []


class BaseProcess:

    async def send_message(self, message, drain=True):
        utils.proto_dumps_std(message, self.stdin)
        if drain:
            return self.stdin.drain()

    async def next_message(self):
        try:
            self.read_task = self._loop.create_task(self.stdout.readline())
            content_type = await self.read_task
            self.read_task = self._loop.create_task(self.stdout.readline())
            content_length = await self.read_task
        except asyncio.CancelledError:
            raise
        else:
            headers = (content_type or b'') + (content_length or b'')
            self.read_task = None
            try:
                if isinstance(content_type, bytes):
                    content_type = content_type.decode('utf8')
                content_type = content_type.split(':')[1].strip()
                if isinstance(content_length, bytes):
                    content_length = content_length.decode('utf8')
                content_length = int(content_length.split(':')[1].strip())
            except IndexError:
                stdout = await self.stdout.read()
                if stdout or headers:
                    print((headers, stdout))
                stderr = await self.stderr.read()
                if stderr:
                    stderr = stderr.decode('utf8')
                    err = stderr.lower()
                    exc = OSError
                    if 'could not resolve hostname' in err:
                        exc = LookupError
                    elif 'host key verification failed' in err:
                        exc = LookupError
                    elif 'permission denied' in err:
                        exc = LookupError
                    exc = exc(stderr, self.host)
                    if isinstance(exc, LookupError):
                        self.host.fail(exc)
                    raise exc

                else:
                    raise ValueError((content_length, stderr))
            data = b''
            while len(data) < content_length:
                try:
                    coro = self.stdout.read(content_length - len(data))
                    self.read_task = self._loop.create_task(coro)
                    data += await self.read_task
                except asyncio.CancelledError:
                    raise
            if content_type == 'zlib':
                data = zlib.decompress(data)
            data = data.decode('utf8')
            try:
                data = utils.json.loads(data)
            except ValueError:
                raise ValueError(data)
            self.host.log.debug5(data)
            if data.get('message_type') == 'exit':
                await self.wait()
                duration = time.time() - self.start
                latency = duration - data['meta']['remote_time']
                self.host.add_time(
                    type='process', cmd=self.cmd,
                    start=self.start, time=duration, latency=latency,
                    task=self.task, meta=data['meta'])
            return data

    async def exit(self):
        if self.returncode is None:
            try:
                await self.wait()
            except asyncio.CancelledError:
                pass
        if getattr(self, '_transport', None):
            for i in (0, 1, 2):
                self._transport.get_pipe_transport(i).close()
        else:
            self.stdin.close()
        self.host.free_session_slot()
        self.host._processes.pop(id(self), None)


class Process(subprocess.Process, BaseProcess):

    def __init__(self, transport, protocol, host, task, cmd, start):
        super().__init__(transport, protocol, host.loop)
        self.host = host
        self.task = task
        self.cmd = cmd
        self.start = start
        self.read_task = None


class SSHClient(asyncssh.SSHClient):

    def __init__(self, uid):
        self.uid = uid
        self.start = time.time()

    def connection_made(self, *args, **kwargs):
        now = time.time()
        asyncssh_connections[self.uid]['connect'] = now - self.start
        self.start = now

    def auth_completed(self, *args, **kwargs):
        asyncssh_connections[self.uid]['auth_time'] = time.time() - self.start


class SSHClientProcess(asyncssh.SSHClientProcess, BaseProcess):

    def __init__(self, host, task, cmd, start):
        super().__init__()
        self._encoding = None
        self.host = host
        self.task = task
        self.cmd = cmd
        self.start = start
        self.read_task = None

    @property
    def returncode(self):
        return self.exit_status


async def get_keys(loop):
    if not asyncssh_keypairs:
        asyncssh_keypairs[:] = [None]
        agent_path = os.environ.get('SSH_AUTH_SOCK', None)
        agent = await asyncssh.connect_agent(
            agent_path, loop=loop)
        asyncssh_keypairs[:] = await agent.get_keys()
        agent.close()
    elif asyncssh_keypairs == [None]:
        while asyncssh_keypairs == [None]:
            await asyncio.sleep(.1)
    return asyncssh_keypairs[:]


def get_known_hosts(filename):
    if not asyncssh_known_hosts:
        known_hosts = asyncssh.known_hosts.read_known_hosts(filename)
        asyncssh_known_hosts[:] = [known_hosts]
    return asyncssh_known_hosts[0]


async def delay_connection(uid, loop):
    if uid not in asyncssh_connections:
        delay = nuka.config['connections']['delay']
        now = time.time()
        asyncssh_connections[uid] = {'now': now, 'timeouts': 0}
        if delay:
            delay = (delay * len(asyncssh_connections))
            min_time = asyncssh_connections.setdefault('time', now) + delay
            delay = min_time - now
            if delay:
                asyncssh_connections[uid]['delay'] = delay
                await asyncio.sleep(delay, loop=loop)


async def create(cmd, host, task=None):
    host.log.debug5(cmd)
    loop = host.loop

    start = time.time()

    if not cmd[0].startswith('ssh') or nuka.cli.args.ssh:
        def protocol_factory():
            return subprocess.SubprocessStreamProtocol(
                loop=loop, limit=DEFAULT_LIMIT)

        await host.acquire_session_slot()
        transport, protocol = await loop.subprocess_exec(
            protocol_factory,
            *cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setpgrp,
            close_fds=True)

        proc = Process(transport, protocol, host, task, cmd, start)
    else:
        def protocol_factory():
            return SSHClientProcess(host, task, cmd, start)

        # retrieve params from ssh command
        tmp_cmd = cmd[:]
        ssh_cmd = tmp_cmd.pop()
        hostname = tmp_cmd.pop()
        agent_forwarding = False
        known_hosts = ()
        attempts = 1
        timeout = 924  # Default TCP Timeout on debian
        while tmp_cmd:
            v = tmp_cmd.pop(0)
            if v == '-l':
                username = tmp_cmd.pop(0)
            elif v == '-p':
                port = tmp_cmd.pop(0)
            elif v in ('-A', '-oForwardAgent=yes'):
                agent_forwarding = True
            elif v == '-oStrictHostKeyChecking=no':
                known_hosts = None
            elif v.startswith('-oConnectionAttempts'):
                attempts = int(v.split('=', 1)[1].strip())
            elif v.startswith('-oConnectTimeout'):
                timeout = int(v.split('=', 1)[1].strip())

        if known_hosts is not None:
            filename = os.path.expanduser('~/.ssh/known_hosts')
            if os.path.isfile(filename):
                try:
                    known_hosts = get_known_hosts(filename)
                except ValueError as e:
                    host.fail(e)
                    msg = ' '.join(e.args)
                    nuka.run_vars['exit_message'] = 'FATAL: ' + msg
                    return

        uid = (username, host)
        conn = asyncssh_connections.get(uid, {}).get('conn')
        if conn is None:
            exc = None
            client_keys = await get_keys(loop)
            asyncssh_connections_tasks[uid] = loop.create_task(
                delay_connection(uid, loop)
            )
            try:
                await asyncssh_connections_tasks[uid]
            except asyncio.CancelledError as e:
                exc = LookupError(OSError('sigint'), host)
                host.fail(exc)
                return

            for i in range(1, attempts + 1):
                host.log.debug5('open connection {0}/{1} at {2}'.format(
                                i, attempts, time.time()))
                try:
                    if nuka.run_vars['sigint']:
                        exc = LookupError(OSError('sigint'), host)
                        break
                    asyncssh_connections_tasks[uid] = loop.create_task(
                        asyncssh.create_connection(
                            lambda: SSHClient(uid),
                            hostname, port,
                            username=username,
                            known_hosts=known_hosts,
                            agent_forwarding=agent_forwarding,
                            client_keys=client_keys,
                            loop=loop,
                            )
                        )
                    conn, client = await asyncio.wait_for(
                            asyncssh_connections_tasks[uid],
                            timeout=timeout, loop=loop)
                    break
                except asyncio.CancelledError as e:
                    exc = LookupError(OSError('sigint'), host)
                    break
                except asyncio.TimeoutError as e:
                    timeouts = asyncssh_connections[uid]['timeouts']
                    asyncssh_connections[uid]['timeouts'] = timeouts + 1
                    if i == attempts:
                        host.log.error('TimeoutError({0}) exceeded '.format(
                            timeout, i, attempts))
                        exc = LookupError(e, host)
                    else:
                        asyncssh_connections_tasks[uid] = loop.create_task(
                            asyncio.sleep(1 + random.random(), loop=loop)
                        )
                        try:
                            await asyncssh_connections_tasks[uid]
                        except asyncio.CancelledError as e:
                            exc = LookupError(e, host)
                            break
                except (OSError, socket.error) as e:
                    exc = LookupError(e, host)
                    break

            if exc is not None:
                host.fail(exc)
                raise exc

            asyncssh_connections[uid]['conn'] = conn
        await host.acquire_session_slot()
        chan, proc = await conn.create_session(
                protocol_factory, ssh_cmd, encoding=None)
        await proc.redirect(asyncssh.PIPE, asyncssh.PIPE, asyncssh.PIPE,
                            DEFAULT_LIMIT)
    host._processes[id(proc)] = proc
    loop.create_task(proc.exit())

    return proc


def close_connections():
    for d in asyncssh_connections.values():
        if isinstance(d, dict):
            if 'conn' in d:
                d['conn'].close()


def close_awaiting_tasks():
    for task in asyncssh_connections_tasks.values():
        if not task.done():
            task.cancel()
