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
import socket
import time
import zlib
import os

import asyncssh
import asyncssh.misc

import nuka
from nuka import utils

DEFAULT_LIMIT = streams._DEFAULT_LIMIT


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


asyncssh_connections = {}
asyncssh_keypairs = []


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


async def create(cmd, host, task=None):
    host.log.debug5(cmd)
    loop = host.loop

    start = time.time()

    if not cmd[0].startswith('ssh') or nuka.cli.args.ssh:
        def protocol_factory():
            return subprocess.SubprocessStreamProtocol(
                loop=loop, limit=DEFAULT_LIMIT)

        await host.acquire_connection_slot()
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
        uid = (username, host)
        conn = asyncssh_connections.get(uid)
        if conn is None:
            exc = None
            client_keys = await get_keys(loop)
            await host.acquire_connection_slot()
            host.log.debug5('open connection at %s', time.time())

            for i in range(1, attempts + 1):
                try:
                    conn, client = await asyncio.wait_for(
                        asyncssh.create_connection(
                            None, hostname, port,
                            username=username,
                            known_hosts=known_hosts,
                            agent_forwarding=agent_forwarding,
                            client_keys=client_keys,
                            loop=loop,
                            ),
                        timeout=timeout, loop=loop)
                except asyncio.TimeoutError as e:
                    host.log.warning('TimeoutError({0}) {1}/{2} '.format(
                        timeout, i, attempts))

                    asyncio.sleep(1, loop=loop)
                except (OSError, socket.error) as e:
                    exc = LookupError(e, host)
                    break

            if conn is None:
                exc = LookupError(
                    'TimeoutError({}). Retries exceeded'.format(timeout),
                    host)
            if exc is not None:
                host.fail(exc)
                raise exc

            asyncssh_connections.setdefault(uid, conn)
        await host.acquire_session_slot()
        chan, proc = await conn.create_session(
                protocol_factory, ssh_cmd, encoding=None)
        await proc.redirect(asyncssh.PIPE, asyncssh.PIPE, asyncssh.PIPE,
                            DEFAULT_LIMIT)
    host._processes[id(proc)] = proc
    loop.create_task(proc.exit())

    return proc


def close_connections():
    for conn in asyncssh_connections.values():
        conn.close()
