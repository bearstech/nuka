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

import time
import codecs
import inspect
import asyncio
import logging
import importlib

import asyncssh.misc

from nuka.remote.task import RemoteTask
from nuka.configuration import config
from nuka import remote
from nuka import utils
from nuka import gpg
import nuka


class Base(asyncio.Future):

    def __init__(self, **kwargs):
        self.initialize(**kwargs)
        super().__init__(loop=self.host.loop)
        if self.host.cancelled():
            self.cancel()
        else:
            self.process()

    def initialize(self, host=None,
                   switch_user=None, switch_ssh_user=None, **args):
        meta = {'filename': None, 'lineno': None,
                'start': time.time(), 'times': [],
                'remote_calls': [],
                }
        for infos in inspect.stack(2):
            f = infos.frame
            if isinstance(f.f_locals.get('self'), RemoteTask):
                continue
            if host is None:
                host = f.f_locals.get('host')
            if switch_user is None:
                switch_user = f.f_locals.get('switch_user')
            if switch_ssh_user is None:
                switch_ssh_user = f.f_locals.get('switch_ssh_user')
            if meta['filename'] is None:
                filename = infos.filename
                if filename.endswith('nuka/task.py'):
                    filename = 'nuka/task.py'
                meta.update(filename=filename,
                            lineno=infos.lineno)
                if host is not None:
                    break
        if host is None:  # pragma: no cover
            raise RuntimeError('No valid host found in the stack')
        self.switch_user = switch_user
        self.switch_ssh_user = switch_ssh_user
        self.meta = meta
        self.host = host
        self.loop = self.host.loop
        self.args = args
        self.res = {'changed': True, 'rc': 0}
        self.start = time.time()
        self.run_task = None
        host.add_task(self)

    def running(self):
        """return True if a remote task is running"""
        if self.run_task is not None:
            return not self.run_task.done()
        return False

    def process(self, fut=None):
        if fut is not None:  # pragma: no cover
            # we waited for boot
            self.meta['start'] = time.time()
        start = time.time()
        try:
            self.pre_process()
        except Exception as e:
            self.host.log.exception(e)
            self.cancel()
            raise
        else:
            duration = time.time() - start
            if duration > .05:  # pragma: no cover
                self.host.add_time(
                    start=start, time=duration,
                    type='pre_process', task=self)
            self.run_task = self._loop.create_task(self._run())

    def pre_process(self):
        """run locally before anything is sent to the host"""

    def post_process(self):
        """run when we get a valid reply from the host"""

    def render_template(self, fd):
        """render a template from a file descriptor:

        .. code-block:: python

            {'src': path, 'dst': path}
        """
        src = fd['src']
        ctx = dict(self.args, **self.args.get('ctx', {}))
        ctx.update(host=self.host, env=config, **fd)
        engine = config.get_template_engine()
        template = engine.get_template(src)
        fd['data'] = template.render(ctx)
        if 'executable' not in fd:
            fd['executable'] = utils.isexecutable(src)

    def render_file(self, fd):
        """render a file from a file descriptor. A file descriptor is a dict:

        .. code-block:: python

            {'src': path, 'dst': path}
        """
        src = fd['src']
        if src.endswith('.gpg'):
            _, data = gpg.decrypt(src, 'utf8')
        else:
            with codecs.open(src, 'r', 'utf8') as fd_:
                data = fd_.read()
        fd['data'] = data
        if 'executable' not in fd:
            fd['executable'] = utils.isexecutable(src)

    def log(self):
        self.host.log.info(self)

    def cancel(self):
        """cancel a task"""
        if not self.cancelled():
            super().cancel()
            if not self.res.get('signal') and not self.host.failed():
                # do not log cancellation if the user wanted it
                self.log()
            if self.run_task is not None:
                self.run_task.cancel()
            self.host.cancel()

    async def _run(self):
        # wrap the task to catch exception
        try:
            await self.run()
        except Exception as e:
            self.cancel()
            if not isinstance(e, asyncio.CancelledError):
                self.host.log.exception5(self)

        # update meta
        self.meta.update(self.res.pop('meta', {}))

        # if task succeded then run post_process
        start = time.time()
        try:
            self.post_process()
        except Exception:
            self.cancel()
            self.host.log.exception5(self)
        finally:
            duration = time.time() - start
            if duration > .05:
                self.host.add_time(
                    start=start, time=duration,
                    type='post_process', task=self)

        # set result / log stuff
        if not self.done():
            self.set_result(self)
            self.meta.setdefault('time', time.time() - self.meta['start'])
            self.host.add_time(type='task', task=self, **self.meta)

        # log if not cancelled
        if not self.cancelled():
            self.log()

    def __bool__(self):
        return self.res.get('rc') == 0

    def __repr__(self):
        return '<{0}>'.format(str(self))

    def __str__(self):
        name = self.__class_name__()
        instance_name = self.args.get('name')
        if instance_name is None:
            instance_name = '-'
        s = '{0}({1})'.format(name, instance_name)
        if self.res:
            if self.res['rc'] == 0:
                if self.cancelled():
                    s += ' cancelled at {filename}:{lineno}'.format(
                        **self.meta)
                elif self.done() and getattr(self, 'changed', True):
                    s += ' changed'
            else:
                s += ' fail({0[rc]})'.format(self.res)
            time = self.meta.get('local_time')
            if time:
                s += ' time({0}s)'.format(round(time, 1))
        return s.strip()

    def __class_name__(self):
        klass = self.__class__
        name = '{0}.{1}'.format(klass.__module__.split('.')[-1],
                                klass.__name__)
        return name


class Task(Base, RemoteTask):

    def process(self):
        if self.host.cancelled():
            self.cancel()
        else:
            diff_mode = self.args.get('diff_mode', nuka.cli.args.diff)
            if diff_mode:
                # ignore diff call if the task do not support it
                attr = getattr(self, 'diff', None)
                if attr in (None, False):
                    self.res['changed'] = False
                    self.meta['local_time'] = 0.
                    if attr is False:
                        self.host.log.info("{0}.diff is False".format(self))
                    else:
                        self.host.log.warning("{0}.diff is None".format(self))
                    self.set_result(self)
                    return
            if self.host.fully_booted.done():
                super().process()
            else:
                # use asyncio with callback since we are in a sync __init__
                task = self.loop.create_task(wait_for_boot(self.host))
                task.add_done_callback(super().process)

    async def run(self):
        """Serialize the task, send it to the remote host.
        The remote script will deserialize the task and run
        :meth:`~nuka.remote.task.Task.do` (or diff() when using --diff)
        """
        self.host.log.debug(self)
        diff_mode = self.args.get('diff_mode', nuka.cli.args.diff)
        klass = self.__class__

        args = {}
        for k, v in self.args.items():
            if k not in ('ctx',):
                args[k] = v

        # prep stdin
        stdin_data = dict(
            task=(klass.__module__, klass.__name__),
            remote_tmp=config['remote_tmp'],
            switch_user=self.switch_user,
            args=args,
            check_mode=False,
            diff_mode=diff_mode,
            log_level=config['log']['levels']['remote_level'])

        if config['testing'] and 'coverage' in self.host.vars:
            # check if we can/want use coverage
            cmd = (
                '{coverage} run -p '
                '--source={remote_dir}/nuka/tasks '
                '{script} '
            ).format(coverage=self.host.vars['coverage'], **config)
        else:
            # use python
            inventory = self.host.vars.get(
                'inventory',
                {'python': {'executable': 'python'}})
            executable = inventory['python'].get('executable', 'python')
            cmd = '{0} {script} '.format(executable, **config)

        # allow to trac some ids from ps
        cmd += '--deploy-id={0} --task-id={1}'.format(config['id'],
                                                      id(self))
        # create process
        proc = await self.host.create_process(
            cmd, task=self,
            switch_user=self.switch_user,
            switch_ssh_user=self.switch_ssh_user)

        # send stdin
        zlib_avalaible = self.host.inventory['python']['zlib_available']
        stdin = utils.proto_dumps_std(
            stdin_data, proc.stdin,
            content_type=zlib_avalaible and 'zlib' or 'plain')
        await proc.stdin.drain()

        res = {}
        while res.get('message_type') != 'exit':
            # wait for messages
            try:
                res = await proc.next_message()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.cancel()
                self.host.log.exception5(
                    '{0}\n\n{1}'.format(self, stdin))
            else:
                if res.get('message_type') == 'log':
                    self.host.log.log(res['level'], res['msg'])

        # finalize
        self.res.update(res)
        if self.res['rc'] != 0 and not self.ignore_errors:
            if not diff_mode:
                self.cancel()

    def log(self):
        log = self.host.log
        if 'exc' in self.res:
            exc = '\n' + ''.join(self.res['exc'])
            log.error('{0}\n{1}'.format(self, exc))
        elif self.res.get('stderr'):
            if self.res.get('rc') != 0:
                log.error('{0}\n{1}'.format(self, self.res['stderr']))
            elif self.res['changed']:
                log.changed('{0}\n{1}'.format(self, self.res['stderr']))
        else:
            data = self.res.get('diff', '')
            if data.strip():
                data = data.strip()
                log.changed('{0} diff=\n{1}\n'.format(self, data))
            elif self.cancelled():
                log.error(self)
            elif self.res['changed']:
                log.changed(self)
            else:
                log.info(self)

        for cmd_ in self.meta.get('remote_calls', []):
            rtime = round(cmd_['time'], 3)
            inf = '^ sh({cmd}) time({rtime})'.format(
                rtime=rtime, **cmd_)
            if cmd_['exc']:
                log.error(inf + '\n' + ''.join(cmd_['exc']))
            elif nuka.cli.args.verbose > 1:
                log.info(inf)
                stds = {k: v for k, v in cmd_.items()
                        if k in ('stderr', 'stdout') and v}
                if stds:
                    log.debug3('^ ' + str(stds))

        data = self.res.get('log')
        if data:
            level = None
            for line in data.rstrip().split('\n'):
                line = line.rstrip()
                try:
                    line_level, message = line.split(':', 1)
                except ValueError:
                    if level:
                        log.log(level, '^ ' + line)
                else:
                    if line_level in logging._nameToLevel:
                        level = getattr(logging, line_level)
                        log.log(level, '^ ' + message)
                    else:
                        if level:
                            log.log(level, '^ ' + line)


class SetupTask(Base):

    changed = False

    def log(self):
        self.host.log.debug(self)

    def pre_process(self):
        self.args['name'] = ''  # unamed task

    def cancel(self):
        super().cancel()
        if not self.host.cancelled():
            self.host.cancel()
            self.host.log.critical(
                'Cancelled at {filename}:{lineno}...'.format(**self.meta))


class boot(SetupTask):
    """A task that just call host.boot()"""

    def __class_name__(self):
        return 'boot'

    async def run(self):
        # wait for boot async
        try:
            await self.host.boot()
        except:
            self.host.log.exception('boot')
        self.meta['start'] = self.host._start


class setup(SetupTask):
    """A task that just wait for :class:`~nuka.task.boot` then setup the
    host"""

    setup_cmd = (
        '{0}rm -Rf {2[remote_tmp]}; '
        '{0}mkdir -p {2[remote_tmp]} && {0}chmod 777 {2[remote_tmp]} &&'
        '{0}mkdir -p {2[remote_dir]} &&'
        'dd bs={1} count=1 | {0}tar -xz -C {2[remote_dir]} && '
        '{0}`which python 2> /dev/null || which python3 || echo python` '
        '{2[script]} --setup'
    )

    def __class_name__(self):
        return 'setup'

    async def run(self):
        host = self.host
        # wait for boot async
        await host._named_tasks[boot.__name__]
        self.meta['start'] = time.time()

        # run bootstrap_command if any
        if host.bootstrap_command:
            res = await host.run_command(host.bootstrap_command)
            if res['rc'] != 0:
                self.host.log.error(res)
                self.cancel()
                return

        # setup
        sudo = ''
        if host.use_sudo:
            sudo = '{sudo} '.format(**config)

        cmd = self.setup_cmd.format(sudo, '{bytes}', config)

        mods = nuka.config['inventory_modules'][:]
        mods += self.host.vars.get('inventory_modules', [])
        if mods:
            cmd += ' ' + ' '.join(['--inventory=' + m for m in mods])

        stdin = remote.build_archive(
            extra_classes=all_task_classes(),
            mode='x:gz')
        c = cmd.format(bytes=len(stdin))
        host.log.debug('Uploading archive ({0}kb)...'.format(
                int(len(stdin) / 1000)))

        try:
            proc = await self.host.create_process(c, task=self)
            proc.stdin.write(stdin)
            await proc.stdin.drain()
        except (LookupError, OSError, asyncssh.misc.Error) as e:
            if isinstance(e, asyncssh.misc.Error):
                e = LookupError(str(e), self.host)
            self.host.log.error(e.args[0])
            self.host.fail(e)
            return

        res = {}
        while res.get('message_type') != 'exit':
            # wait for messages
            try:
                res = await proc.next_message()
            except asyncio.CancelledError:
                raise
            except (LookupError, OSError) as e:
                self.host.log.error(e.args[0])
                self.host.fail(e)
                return
            except Exception as e:
                self.cancel()
                self.host.log.exception5(
                    '{0}\n\n{1}'.format(self, stdin))
            else:
                if res.get('message_type') == 'log':
                    self.host.log.log(res['level'], res['msg'])

        self.res.update(res)

        if self.res['rc'] != 0:
            self.cancel()

        host.vars['inventory'] = self.res['inventory']
        for name in mods:
            mod = importlib.import_module(name)
            meth = getattr(mod, 'finalize_inventory', None)
            if meth is not None:
                meth(host.vars['inventory'])
        host.log.debug(
            'Inventory:\n{0}'.format(host.vars['inventory']))

        if not host.fully_booted.done():
            host.fully_booted.set_result(True)


class teardown(SetupTask):
    """remove `remote_dir` from the host"""

    teardown_cmd = '{0}rm -Rf {1[remote_dir]}'

    def __init__(self, host):
        host._cancelled = False
        super().__init__(host=host)

    def __class_name__(self):
        return 'teardown'

    async def run(self):
        if not self.host.failed():
            sudo = self.host.use_sudo and 'sudo ' or ''
            cmd = self.teardown_cmd.format(sudo, config)
            await self.host.run_command(cmd, task=self)


class destroy(SetupTask):
    """destroy the host"""

    def __init__(self, host):
        host._cancelled = False
        super().__init__(host=host)

    def __class_name__(self):
        return 'destroy'

    async def run(self):
        if 'destroyed' not in self.host.vars:
            await self.host.destroy()


class wait(Base):
    """A task that wait for a coroutine / event / future:

    .. code-block:: python

        nuka.wait(do_something(host), event)

    You can use a timeout:

    .. code-block:: python

        nuka.wait(event, timeout=30)

    """

    def __class_name__(self):
        return 'wait'

    def __init__(self, future, *futures, **kwargs):
        futures = list(futures)
        if not isinstance(future, list):
            futures.insert(0, future)
        else:
            futures[0:0] = future
        kwargs['name'] = repr(futures)
        kwargs['futures'] = futures
        super().__init__(**kwargs)

    async def run(self):
        futures = self.args['futures']

        res = await asyncio.wait_for(asyncio.gather(*futures),
                                     timeout=self.args.get('timeout'))

        self.set_result(res)
        self.meta.setdefault('time', time.time() - self.meta['start'])

        # skip time if we dont wait for a nuka.Event
        events = [e for e in res if isinstance(e, nuka.Event)]
        if events:
            self.host.add_time(type='task', task=self, **self.meta)


async def wait_for_boot(host):
    if not host.fully_booted.done():
        create_setup_tasks(host)
        task = host._named_tasks[setup.__name__]
        if not task.done():
            await task


def create_setup_tasks(host):
    if not host.fully_booted.done():
        for task in (boot, setup):
            instance = host._named_tasks.get(task.__name__)
            if instance is None:
                instance = task(host=host)
                host._named_tasks[task.__name__] = instance
                host._tasks.append(instance)


def get_task_from_stack():
    for info in inspect.stack(3):
        f = info.frame
        self = f.f_locals.get('self')
        if isinstance(f.f_locals.get('self'), Base):
            return self


def all_task_classes(cls=Task):
    for klass in cls.__subclasses__():
        yield from all_task_classes(klass)
        yield klass
