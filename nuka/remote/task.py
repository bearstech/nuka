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

from __future__ import unicode_literals
import os
import sys
import time
import codecs
import signal
import select
import difflib
import logging
import subprocess

from nuka import utils


def safe_iterator(iterator=None):
    while True:
        if iterator is not None:
            try:
                utils._next(iterator)
            except:
                logging.exception(iterator)
        yield


class RemoteTask(object):

    stdin = getattr(sys.stdin, 'buffer', sys.stdin)
    logfile = utils.StringIO()

    ignore_errors = False

    def __getattr__(self, attr):
        if attr.startswith('_'):
            raise AttributeError(attr)
        try:
            return self.res[attr]
        except KeyError:
            raise AttributeError(attr)


class Task(RemoteTask):
    """Remote task"""

    current_process_watcher = None
    current_process = None
    current_cmd = None

    process_watcher_delay = 2

    alarm_delay = 1
    alarm_count = 0

    remote_start = time.time()
    remote_calls = []

    stds = dict(
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    def __init__(self, **kwargs):
        self.start = time.time()
        self.res = {}
        self.args = kwargs

    @classmethod
    def texts_diff(self, old_text, new_text, **kwargs):
        old_list = old_text.splitlines(1)
        new_list = new_text.splitlines(1)
        res = self.lists_diff(old_list, new_list, **kwargs)
        return res

    @classmethod
    def lists_diff(self, old_list, new_list,
                   fromfile='(old)', tofile='(new)', **kwargs):
        res = difflib.unified_diff(
            old_list, new_list, fromfile=fromfile, tofile=tofile, **kwargs)
        return ''.join(res)

    @classmethod
    def get_inventory(self):
        dirname = os.path.dirname(sys.argv[0])
        cache = os.path.join(dirname, 'inventory.json')
        data = self.get()
        with codecs.open(cache) as fd:
            utils.json.read(data, fd)
        return data

    @property
    def is_debian(self):
        return os.path.isfile('/etc/debian_version')

    @property
    def is_centos(self):
        return os.path.isfile('/etc/centos-release')

    def do(self):
        """called on the remote host.
        Task arguments are available in self.args
        Must return a dict like::

            {'rc': 0, 'changed': False}
        """
        raise NotImplementedError()

    @classmethod
    def sh(self, args, stdin=b'', shell=False, env=None, check=True,
           watcher=None, short_args=None, stdout=None, stderr=None):
        """run a shell command"""
        start = time.time()
        env_ = os.environ.copy()
        env_.update(LC_ALL='C', LANG='C')
        if env:
            env_.update(env)
        kwargs = dict(self.stds, shell=shell)
        if stdout is not None:
            kwargs['stdout'] = stdout
        if stderr is not None:
            kwargs['stderr'] = stderr
        res = {'stdout': '', 'stderr': ''}
        try:
            p = subprocess.Popen(args, env=env_, **kwargs)
        except Exception:
            rc = res['rc'] = 1
            exc = self.format_exception()
        else:
            self.current_cmd = short_args or args
            self.current_process = p
            if watcher is not None:
                self.current_process_watcher = safe_iterator(watcher(self, p))
            else:
                self.current_process_watcher = safe_iterator()
            if stdin and not isinstance(stdin, bytes):
                stdin = stdin.encode('utf8')
            stdout, stderr = p.communicate(stdin)
            self.current_process = None
            utils._next(self.current_process_watcher)
            self.current_process_watcher = None
            if stdout is None:
                stdout = kwargs['stdout']
                with open(stdout.name) as fd:
                    try:
                        stdout = fd.read()
                    except OSError:
                        stdout = ''
            if isinstance(stdout, bytes):
                stdout = stdout.decode('utf8')
            if stderr is None:
                stderr = kwargs['stderr']
                with open(stderr.name) as fd:
                    try:
                        stderr = fd.read()
                    except OSError:
                        stderr = ''
            if isinstance(stderr, bytes):
                stderr = stderr.decode('utf8')
            rc = p.returncode
            res.update(rc=rc, stdout=stdout, stderr=stderr)
            exc = None
        t = time.time() - start
        self.remote_calls.append(dict(res, cmd=args, start=start, time=t,
                                      exc=exc))
        if check:
            return self.check(res)
        return res

    @classmethod
    def format_exception(self):
        import traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        return traceback.format_exception(exc_type, exc_value,
                                          exc_traceback)

    @classmethod
    def on_alarm(self, *args):
        self.alarm_count += 1
        ready = select.select([sys.stdin], [], [], .0)[0]
        if ready:
            try:
                data = utils.proto_loads_std(self.stdin)
            except ValueError:
                pass
            else:
                sig = data.get('signal')
                if sig is not None:
                    self.on_sigint()
        if self.alarm_count % self.process_watcher_delay == 0:
            if self.current_process_watcher is not None:
                utils._next(self.current_process_watcher)
        signal.alarm(self.alarm_delay)

    @classmethod
    def on_sigint(self, *args):
        res = dict(rc=1, signal='SIGINT', current_process=None)
        if self.current_process is not None:
            # forward signal to current process if any
            p = self.current_process
            p.send_signal(signal.SIGINT)
            # let the watcher know that we no longer have a process
            if self.current_process_watcher is not None:
                self.current_process = None
                utils._next(self.current_process_watcher)
            p.wait()
            res['current_process'] = {
                'cmd': self.current_cmd,
                'pid': p.pid,
                'rc': p.returncode}
        # clean exit
        self.exit(res)

    @classmethod
    def is_alive(self, process):
        """return True iif the process is the current process"""
        if self.current_process is not None:
            return self.current_process.pid == process.pid

    @classmethod
    def send_progress(self, value, level=utils.PROGRESS):
        """send progression of the current remote process to the client"""
        if self.current_process is not None:
            p = self.current_process
            if p.returncode is None:
                message = 'sh({cmd}, pid={pid}) {value}'.format(**{
                    'cmd': ' '.join(self.current_cmd),
                    'pid': p.pid,
                    'value': value,
                    })
                self.send_log(message, level=level)

    @classmethod
    def send_log(self, message, level=logging.DEBUG):
        """send a log line to the client"""
        self.send_message(dict(message_type='log', msg=message, level=level))

    @classmethod
    def send_message(self, message):
        if 'message_type' not in message:
            raise ValueError(
                'No message_type specified in {0}'.format(message))
        utils.proto_dumps_std_threadsafe(message, sys.stdout)
        sys.stdout.flush()

    @classmethod
    def exit(self, res):
        # tel the watcher that the process is ended
        if self.current_process_watcher is not None:
            self.current_process = None
            utils._next(self.current_process_watcher)
        res.setdefault('rc', 0)
        res.setdefault('message_type', 'exit')
        res.setdefault('signal', None)
        res['meta'] = dict(
            remote_calls=self.remote_calls,
            remote_time=time.time() - self.remote_start
        )
        self.logfile.seek(0)
        logs = self.logfile.read()
        if logs.strip():
            res['log'] = logs
        if 'diff' in res:
            res.setdefault('changed', bool(res['diff']))
        utils.proto_dumps_std_threadsafe(res, sys.stdout)
        sys.exit(0)

    @classmethod
    def check(self, res):
        if res.get('rc') != 0:
            self.exit(res)
        return res

    @classmethod
    def from_dict(cls, data):
        args = data['args']
        ob = cls(**args)
        return ob
