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
import time
import os

from nuka import utils

DEFAULT_LIMIT = streams._DEFAULT_LIMIT


class Process(subprocess.Process):

    def __init__(self, transport, protocol, host, task, cmd, start):
        super().__init__(transport, protocol, host.loop)
        self.host = host
        self.task = task
        self.cmd = cmd
        self.start = start
        self.read_task = None

    async def send_message(self, message, drain=True):
        utils.proto_dumps_std(message, self.stdin)
        if drain:
            return self.stdin.drain()

    async def next_message(self):
        try:
            self.read_task = self._loop.create_task(self.stdout.readline())
            header = await self.read_task
        except asyncio.CancelledError:
            raise
        else:
            self.read_task = None
            length = header.split(b': ')
            try:
                l = int(length[1].strip())
            except IndexError:
                stdout = await self.stdout.read()
                if stdout or header:
                    print((header, stdout))
                stderr = await self.stderr.read()
                if stderr:
                    raise OSError(stderr)
                else:
                    raise ValueError((length, stderr))
            data = b''
            while len(data) < l:
                try:
                    coro = self.stdout.read(l - len(data))
                    self.read_task = self._loop.create_task(coro)
                    data += await self.read_task
                except asyncio.CancelledError:
                    raise
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
        try:
            await self.wait()
        except asyncio.CancelledError:
            pass
        if self.returncode != 0:
            # cancel read if the process fail
            if self.read_task is not None:
                if not self.read_task.done():
                    self.read_task.cancel()
            # ensure fd are closed
            for i in (0, 1, 2):
                self._transport.get_pipe_transport(i).close()
            # clean host links
        self.host.free_session_slot()
        self.host._processes.pop(id(self), None)


async def create(cmd, host, task=None):
    await host.acquire_session_slot()
    host.log.debug5(cmd)

    start = time.time()

    def protocol_factory():
        return subprocess.SubprocessStreamProtocol(
            loop=host.loop, limit=DEFAULT_LIMIT)

    transport, protocol = await host.loop.subprocess_exec(
        protocol_factory,
        *cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setpgrp,
        close_fds=True)

    proc = Process(transport, protocol, host, task, cmd, start)
    host._processes[id(proc)] = proc
    proc._loop.create_task(proc.exit())

    return proc
