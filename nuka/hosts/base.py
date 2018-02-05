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

import os
import sys
import time
import asyncio
import resource
from operator import itemgetter
from collections import deque
from collections import OrderedDict

import nuka
from nuka import log
from nuka import process
from nuka.task import wait_for_boot
from nuka.task import get_task_from_stack
from nuka.task import destroy as destroy_task

RLIMIT_NOFILE = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
resource.setrlimit(resource.RLIMIT_NOFILE, (RLIMIT_NOFILE, RLIMIT_NOFILE))
MAX_PROCESSES = int(RLIMIT_NOFILE / 4)


class HostGroup(OrderedDict):
    """A dict like object to group hosts"""

    async def boot(self):
        raise NotImplementedError()

    async def destroy(self):  # pragma: no cover
        hosts = list(self.values())
        if hosts:
            return await asyncio.wait([destroy_task(h) for h in hosts])

    def __repr__(self):
        return repr([k for k in self])


all_hosts = HostGroup()
nuka.config['all_hosts'] = all_hosts


class TimeIt(object):

    def __init__(self, host, task=None, **kwargs):
        if task is None:  # pragma: no cover
            task = get_task_from_stack()
        kwargs['task'] = task
        self.start = None
        self.host = host
        self.kwargs = kwargs

    def __enter__(self, *args, **kwargs):
        self.start = time.time()

    def __exit__(self, *args, **kwargs):
        self.host.add_time(start=self.start, **self.kwargs)


class BaseHost(object):

    provider = None
    processes_count = 0
    stds = dict(
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    def __init__(self, hostname=None, port='22', **vars):
        if 'address' in vars:
            self.name = self.hostname = vars.pop('address')
        else:
            self.name = hostname.split('.', 1)[0]
            self.hostname = hostname
        self.name = vars.get('name', self.name)
        self.vars = vars
        self.max_sessions = int(self.vars.pop('max_sessions', 10))
        self.vars.setdefault('user', 'root')
        self.vars.setdefault('port', '22')
        self.vars.setdefault('use_sudo', False)
        self.vars.setdefault('archive_modes', ('x:gz',))

        self.loop = vars.pop('loop', asyncio.get_event_loop())

        self._sessions = deque()
        self._cancelled = False
        self._failed = None
        self._start = time.time()
        self._processes = {}
        self._tasks = []
        self._named_tasks = {}
        self._task_times = []
        self._start = time.time()
        self._log = None

        logger = self.vars.pop('logger', None)
        if logger is not None:  # pragma: no cover
            self._log = logger

        self.fully_booted = asyncio.Future(loop=self.loop)

        all_hosts[self.name] = self

    @property
    def log(self):
        if self._log is None:
            self._log = log.HostLogger(self)
        return self._log

    def add_task(self, task):
        self._tasks.append(task)

    def running_tasks(self):
        return [t for t in self._tasks if t.running()]

    def timeit(self, task=None, **kwargs):
        return TimeIt(self, task=task, **kwargs)

    def add_time(self, start=None, task=None, **kwargs):
        kwargs.setdefault('time', time.time() - start)
        if task is None:  # pragma: no cover / maybe no longer required
            task = get_task_from_stack()
        if task is not None:
            kwargs.update(start=start, task=task)
            self._task_times.append(kwargs)
        else:  # pragma: no cover
            self.log.warning("can't retrieve task\n{}".format(kwargs))

    def cancel(self):
        for task in self.running_tasks():
            if not task.done():  # pragma: no cover
                task.cancel()
        self._cancelled = True

    def cancelled(self):
        return self._cancelled

    def fail(self, exc):
        if not self._failed:
            self.cancel()
            self._failed = exc

    def failed(self):
        return self._failed

    def _get_best_addresses(self, public=True):
        hvars = self.vars
        key = public and 'public_ip' or 'private_ip'
        try:
            return hvars[key]
        except KeyError:
            pass
        ifaces = hvars.get('inventory', {}).get('ifaces', {})
        for iface in sorted(ifaces.values(), key=itemgetter('index')):
            if not iface.get('macaddress'):
                # tunX
                continue
            for net in iface.get('inet', []):
                if iface['primary']:
                    if net['is_private']:
                        hvars['private_ip'] = net['address']
                    else:
                        hvars['public_ip'] = net['address']
                elif not net['is_private'] and 'public_ip' not in hvars:
                    hvars['public_ip'] = net['address']
                elif net['is_private'] and 'private_ip' not in hvars:
                    hvars['private_ip'] = net['address']
        return hvars.get(key)

    @property
    def public_ip(self):
        """return host's public ip"""
        return self._get_best_addresses(public=True)

    @property
    def private_ip(self):
        """return host's private ip"""
        return self._get_best_addresses(public=False)

    def __getattr__(self, attr):
        return self.vars[attr]

    def __str__(self):
        return self.name

    def __repr__(self):
        s = '<{0} {1}'.format(self.__class__.__name__, self.name)
        if self.cancelled():
            s += ' cancelled'
        s += '>'
        return s

    @property
    def bootstrap_command(self):
        return self.vars.get('bootstrap_command')

    async def boot(self):  # pragma: no cover
        """boot the host"""
        return dict(rc=0)

    async def get_inventory(self):  # pragma: no cover
        """return host's inventory. await for host's boot & setup if needed"""
        if not self.fully_booted.done():
            await wait_for_boot(self)
        return self.vars['inventory']

    async def destroy(self):  # pragma: no cover
        """destroy the host"""
        self.vars['destroyed'] = True
        return dict(rc=0)

    async def acquire_session_slot(self):
        while self.processes_count > MAX_PROCESSES:
            self.log.debug5('wait for free fds')
            await asyncio.sleep(.5, loop=self.loop)
        sessions = self._sessions
        ll = len(sessions)
        if ll >= self.max_sessions:  # pragma: no cover
            self.log.debug5('wait for a session')
            while ll >= self.max_sessions:
                if not self.cancelled():
                    await asyncio.sleep(.5, loop=self.loop)
                else:
                    return sessions
                ll = len(sessions)
        self.__class__.processes_count += 1
        sessions.append(1)

    def free_session_slot(self):
        self.__class__.processes_count -= 1
        self._sessions.pop()

    async def create_process(self, cmd, task=None, **kwargs):
        if self.cancelled():
            raise asyncio.CancelledError()
        process_cmd = self.wraps_command_line(cmd, **kwargs)
        proc = await process.create(process_cmd, self, task)
        return proc

    async def run_command(self, cmd=None, stdin=None, task=None, **kwargs):
        """run a shell command on the remote host"""
        proc = await self.create_process(cmd, task)
        if stdin:
            proc.stdin.write(stdin)
            await proc.stdin.drain()
            # close_stdin is not recommended. we cant send signals after that
            # but it's usefull for testing
            if kwargs.get('close_stdin'):
                proc.stdin.close()
        stdout, stderr = await asyncio.gather(proc.stdout.read(),
                                              proc.stderr.read(),
                                              loop=self.loop)
        if kwargs.get('wait', True):
            await proc.wait()
        return dict(rc=proc.returncode, stdout=stdout, stderr=stderr)

    async def send_messages(self, message):  # pragma: no cover
        coros = []
        for proc in self._processes.values():
            try:
                coro = proc.send_message(message)
            except ConnectionResetError:
                pass
            else:
                coros.append(coro)
        if coros:
            try:
                await asyncio.wait(coros)
            except ConnectionResetError:
                pass

    @classmethod
    def from_stdin(cls):
        for line in sys.stdin:
            yield cls(hostname=line.strip())


class Host(BaseHost):
    """A host. Used by tasks as target"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not os.getenv('SSH_AUTH_SOCK'):
            self.log.warning('No SSH_AUTH_SOCK set. Your tasks may freeze')

    def wraps_command_line(self, cmd, **kwargs):
        ssh_user = kwargs.get('switch_ssh_user')
        if ssh_user is None:
            # we use the main user account
            switch_user = kwargs.get('switch_user') or 'root'
            if switch_user != 'root':
                if switch_user != self.vars['user']:
                    # we have to use sudo
                    args = (switch_user, cmd)
                    if self.use_sudo:
                        cmd = '{sudo} -u {0} {1}'.format(*args, **nuka.config)
                    else:
                        cmd = '{su} -c "{1}" {0}'.format(*args, **nuka.config)
            elif self.use_sudo:
                cmd = '{sudo} {0}'.format(cmd, **nuka.config)

        if ssh_user is None:
            ssh_user = self.vars['user']

        ssh_cmd = ['ssh'] + nuka.config['ssh']['options'] + ['-l', ssh_user]
        if self.port:
            ssh_cmd.extend(['-p', self.port])
        ssh_cmd.extend([self.hostname, cmd])
        return ssh_cmd


class LocalHost(BaseHost):

    def __init__(self):
        super().__init__(hostname='localhost')

    def wraps_command_line(self, cmd, **kwargs):
        ssh_cmd = ['bash', '-c', cmd]
        return ssh_cmd


class Chroot(BaseHost):

    def __init__(self, path):
        super().__init__(hostname=path.split('/')[-1])
        self.path = path

    def wraps_command_line(self, cmd, **kwargs):
        ssh_cmd = ['chroot', self.path, 'bash', '-c', cmd]
        return ssh_cmd
