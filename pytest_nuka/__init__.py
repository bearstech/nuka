# -*- coding: utf-8 -*-
import os
import pytest
import asyncio
import logging

from nuka.tasks.user import (create_user, delete_user)
from nuka.task import wait_for_boot
from nuka.hosts import DockerContainer
from nuka.hosts import Vagrant
import nuka

nuka.config['log']['dirname'] = '.nuka/logs'
nuka.config['log']['levels'] = {
    'stream_level': logging.DEBUG,
    'file_level': logging.DEBUG,
    'remote_level': logging.DEBUG,
}


@pytest.yield_fixture(scope='session')
def session_container(request):
    loop = asyncio.get_event_loop()
    ENV_NAME = os.environ['ENV_NAME']
    if ENV_NAME.endswith('vagrant'):
        h = Vagrant()
    else:
        PY, IMAGE, TAG = ENV_NAME.split('-', 2)
        if IMAGE == 'nukai':
            IMAGE = 'bearstech/nukai'
        DOCKER_IMAGE = '{0}:{1}'.format(IMAGE, TAG)
        DOCKER_NAME = DOCKER_IMAGE.replace(':', '-').replace('/', '-')
        h = DockerContainer(
            hostname=DOCKER_NAME,
            image=DOCKER_IMAGE,
            command=['bash', '-c', 'while true; do sleep 1000000000000; done'],
        )
        loop.run_until_complete(wait_for_boot(h))
    # check if we can use coverage
    res = loop.run_until_complete(
        h.run_command('ls {remote_dir}/bin/coverage'.format(**nuka.config)))
    if res['rc'] == 0 and 'vagrant' not in ENV_NAME:
        h.vars['coverage'] = '{remote_dir}/bin/coverage'.format(**nuka.config)

    yield h

    # FIXME: get coverage results
    if 'coverage' in h.vars and 'vagrant' not in ENV_NAME:
        loop = asyncio.new_event_loop()
        h.loop = loop
        h._cancelled = False
        loop.run_until_complete(
            h.run_command('{coverage} combine; true'.format(**h.vars),
                          wait=False))
        res = loop.run_until_complete(
            h.run_command('cat .coverage', wait=False))
        data = res['stdout'].decode('utf8')
        for script in ('script.py', 'plugin.py'):
            data = data.replace(
                os.path.join(nuka.config['remote_dir'], 'nuka', script),
                os.path.join(os.path.dirname(nuka.__file__),
                             'remote', script)
            )
        data = data.replace(
            os.path.join(nuka.config['remote_dir'], 'nuka'),
            os.path.dirname(nuka.__file__))
        filename = os.environ['COVERAGE_REMOTE_FILE']
        if os.path.isfile(filename):
            filename += '.1'
        with open(filename, 'wb') as fd:
            fd.write(data.encode('utf8'))


@pytest.yield_fixture(scope='function')
def host(request, session_container, event_loop):
    session_container._cancelled = False
    session_container.log.warning(
        '============ START {0} =============='.format(request.function))
    session_container.loop = event_loop
    yield session_container
    session_container.log.warning(
        '============ END {0} =============='.format(request.function))


@pytest.yield_fixture(scope='function')
def user(request, host):
    host._cancelled = False
    try:
        host.loop.run_until_complete(asyncio.wait_for(
            delete_user('test_user', host=host),
            timeout=5))
    except RuntimeError:
        pass
    host.loop.run_until_complete(asyncio.wait_for(
        create_user(username='test_user', host=host),
        timeout=20))
    yield 'test_user'
    host._cancelled = False
    try:
        host.loop.run_until_complete(asyncio.wait_for(
            delete_user('test_user', host=host),
            timeout=5))
    except RuntimeError:
        pass


@pytest.fixture(scope='session')
def wait(request):
    def wait(coro, timeout=.5):
        return asyncio.wait_for(coro, timeout)
    return wait


class _diff_mode:

    def __enter__(self, *args, **kwargs):
        nuka.cli.args.diff = True

    def __exit__(self, *args, **kwargs):
        nuka.cli.args.diff = False

    def __call__(self, value):
        nuka.cli.args.diff = value


@pytest.yield_fixture(scope='function')
def diff_mode(request):
    yield _diff_mode()
    nuka.cli.args.diff = False
