# -*- coding: utf-8 -*-
"""

nuka.run
========

.. autofunction:: run

nuka.wait
==========

.. autoclass:: wait

nuka.Event
===========

.. autoclass:: Event

nuka.cancel_on_error
====================

.. autofunction:: cancel_on_error
"""
import concurrent
import functools
import logging
import asyncio
import atexit
import signal
import shutil
import sys
import os

import uvloop

# api
from nuka.cli import cli
from nuka import reports
from nuka import process
from nuka import utils  # NOQA / API
from nuka.task import wait  # NOQA / API
from nuka.task import teardown
from nuka.configuration import config

sleep = asyncio.sleep  # NOQA / API


run_vars = {}


class Event(asyncio.Future):
    """A named event that you can wait:

    .. code-block:: python

        event = Event('myevent')

        async def do_something(host):
            nuka.wait(event)
    """

    def __init__(self, name, loop=None):
        self.name = str(name)
        super().__init__(loop=loop)
        self.res = {}

    def set_result(self, **kwargs):
        """update Event.res' dict with kwargs and release the event"""
        self.res.update(kwargs)
        super().set_result(kwargs)

    def release(self):
        """release the event"""
        self.set_result()

    def __repr__(self):
        s = super().__repr__()
        s = s.replace('<Event ', '<Event {0} '.format(self.name))
        return s


def cancel_on_error(*futures):
    """Cancel futures when the coroutine raise:

    .. code-block:: python

        @cancel_on_error(event)
        async def do_something(host):
            event.release()
    """
    def wrapper(func):
        @functools.wraps(func)
        async def do(host, *args, **kwargs):
            try:
                return await func(host, *args, **kwargs)
            except asyncio.CancelledError:
                for f in futures:
                    if not f.done():
                        f.cancel()
                raise
            except:
                host.log.exception(func)
                for f in futures:
                    if not f.done():
                        f.cancel()
        return do
    return wrapper


def run(*coros, timeout=None):
    """Run coroutines:

    .. code-block:: python

        nuka.run(do_something(host)
    """
    # parse args if not already done
    if cli.args is None:
        cli.parse_args()

    # register signal if not already done
    if 'sigint' not in run_vars:
        run_vars['sigint'] = 0
        loop.add_signal_handler(signal.SIGINT, on_sigint)

    to_run = []

    for coro in coros:
        host = None
        try:
            host = coro.cr_frame.f_locals.get('host')
        except:
            pass
        if host is not None and not host.failed():
            host.log('{0}({1})'.format(coro.__name__, host))
        to_run.append((host, coro))
    coro = asyncio.gather(*[c for h, c in to_run],
                          loop=loop, return_exceptions=True)
    coro = asyncio.wait_for(coro, loop=loop, timeout=timeout)
    try:
        results = loop.run_until_complete(coro)
    except Exception as e:
        raise asyncio.CancelledError()
    else:
        res_with_exc = []
        for (host, coro), res in zip(to_run, results):
            if isinstance(res, asyncio.CancelledError):
                if host is not None:
                    if host.failed():
                        res = host.failed()
                if not isinstance(res, LookupError):
                    sys.exit(1)
            elif isinstance(res, Exception):
                raise res
            res_with_exc.append(res)
        return res_with_exc


def run_all(coro, *hosts, **kwargs):
    return run(*[coro(h) for h in hosts], **kwargs)


def on_sigint(*args, **kwargs):
    hosts = config['all_hosts'].values()
    run_vars['sigint'] = run_vars['sigint'] + 1
    if run_vars['sigint'] == 1:
        process.close_awaiting_tasks()
        logging.warning('Exiting...')
        all_tasks = 0
        for host in hosts:
            tasks = host.running_tasks()
            if not host.fully_booted.done():
                host.log.info('Cancelling {0}...'.format(tasks))
                executor.shutdown(wait=False)
            else:
                all_tasks += len(tasks)
                if tasks:
                    host.log.info('Waiting for {0}...'.format(tasks))
            # do not use host.cancel() because we don't want to cancel running
            # tasks
            host._cancelled = True
    elif run_vars['sigint'] == 2:
        logging.warning('Killing remote processes...')
        for host in hosts:
            loop.create_task(host.send_messages(dict(signal='SIGINT')))
    elif run_vars['sigint'] > 2:
        logging.warning('Exploding...')
        executor.shutdown(wait=False)
        sys.exit(1)


def on_exit():
    if cli.finalized and not cli.help:
        if 'all_hosts' in config and 'remote_dir' in config:
            hosts = config['all_hosts'].values()
            hosts = [h for h in hosts if h._tasks]
            coros = [teardown(host=h) for h in hosts if h.loop is loop]
            if coros:
                loop.run_until_complete(asyncio.wait(coros))
            if hosts:
                reports.build_reports(hosts)
        executor.shutdown(wait=True)
        process.close_connections()
        loop.close()
        dirname = config['tmp']
        if os.path.isdir(dirname):
            shutil.rmtree(dirname)
    if 'exit_message' in run_vars:
        print(run_vars['exit_message'])


# do no use cli to parse this option sinc we need the loop early
if '--uvloop' in sys.argv:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    level = logging.WARNING
elif '--debug' in sys.argv:
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    level = logging.DEBUG
else:
    loop = asyncio.get_event_loop()
    level = logging.WARNING

logging.basicConfig(stream=sys.stdout, level=level,
                    format='%(levelname)-5.5s: %(message)s')

# explicit executor that we can shutdown gracefully
executor = concurrent.futures.ThreadPoolExecutor(5)
loop.set_default_executor(executor)


if 'TESTING' not in os.environ:
    # do nothing on exit while unittests
    atexit.register(on_exit)
