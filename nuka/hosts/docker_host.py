# -*- coding: utf-8 -*-
from functools import partial
import subprocess
import asyncio
import sys

import docker as docker_py

from nuka.task import get_task_from_stack
from nuka.hosts.base import BaseHost
from nuka.hosts.base import HostGroup
from nuka.task import wait_for_boot
import nuka

try:
    DockerClient = docker_py.Client
except AttributeError:
    DockerClient = docker_py.APIClient


class DockerContainer(BaseHost):
    """By default the image will be ``bearstech/nukai:latest`` which is the
    latest debian with python3 installed but you can use whatever you want. We
    also provide a bunch of `nukai(mages)
    <https://hub.docker.com/r/bearstech/nukai/tags/>`_

    .. code-block:: py

        >>> host = DockerContainer(
        ...     hostname='myhost',
        ...     image='bearstech/nukai:debian-jessie-python3')
    """

    provider = 'docker'

    def __init__(self, hostname=None, image='bearstech/nukai:latest',
                 **kwargs):
        kwargs.update(hostname=hostname, image=image)
        super().__init__(**kwargs)
        self.cli = DockerClient()

    @property
    def bootstrap_command(self):
        if 'bootstrap_command' in self.vars:
            return self.vars['bootstrap_command']
        elif self.vars['image'].startswith('debian'):
            return (
                'which python || (apt-get update -qq > /dev/null; '
                ' apt-get install -qqy '
                'python-virtualenv wget perl-modules adduser)'
            )
        elif self.vars['image'].startswith('centos'):
            return (
                'ls /usr/bin/wget 2>&1 > /dev/null || '
                'yum install -y -q -q wget 2>&1 > /dev/null;'
                'ls /usr/bin/virtualenv 2>&1 > /dev/null || '
                'yum install -y -q -q python-virtualenv 2>&1 > /dev/null'
            )

    async def acquire_session_slot(self):
        return

    async def acquire_connection_slot(self):
        return

    def free_session_slot(self):
        return

    def wraps_command_line(self, cmd, **kwargs):
        # there is no ssh in docker so we use the regular switch_user
        ssh_user = kwargs.get('switch_ssh_user')
        if ssh_user is not None:
            kwargs['switch_user'] = ssh_user

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

        cmd = ['docker', 'exec', '-i', str(self), 'bash', '-c', cmd]
        return cmd

    async def boot(self):
        # we need to get the task from here.
        # we cant retrieve it while in an executor
        task = get_task_from_stack()
        boot = partial(self._boot_api, task=task)
        return await self.loop.run_in_executor(None, boot)

    def _boot_api(self, task=None):
        with self.timeit(type='api_call', task=task, name='start()'):
            try:
                self.cli.start(self.name)
            except docker_py.errors.APIError:
                pass
        with self.timeit(type='api_call', task=task, name='containers()'):
            containers = self.cli.containers(filters=dict(name=self.name))
        if containers:
            container = containers[0]
        else:
            with self.timeit(type='api_call', task=task, name='images()'):
                found = False
                for image in self.cli.images():
                    if image['RepoTags'] == [self.image]:
                        found = True
            if not found:
                with self.timeit(type='api_call', task=task, name='pull()'):
                    self.log.warning('Pulling image {0}...'.format(self.image))
                    subprocess.call(['docker', 'pull', self.image])
            self.log.debug('Create container...')
            with self.timeit(type='api_call', task=task, name='create()'):
                container = self.cli.create_container(
                    image=self.image,
                    name=self.name, hostname=self.name,
                    command=self.vars.get('command', None))
        self.vars['container'] = container
        self.vars['container_id'] = container['Id']
        try:
            self.cli.start(self.name)
        except docker_py.errors.APIError:
            pass
        else:
            self.log.debug('Container started'.format(self))
        return container

    @property
    def private_ip(self):
        if 'private_ip' not in self.vars:
            container = self.vars['container']
            net = list(container['NetworkSettings']['Networks'].values())[0]
            ip = net['IPAddress']
            # containers has no public ip
            self.vars['public_ip'] = self.vars['private_ip'] = ip
        return self.vars['private_ip']
    public_ip = private_ip

    async def destroy(self):
        remove_container = partial(self.cli.remove_container,
                                   self.hostname, force=True)
        await self.loop.run_in_executor(None, remove_container)


class DockerCompose(HostGroup):
    """A HostGroup that use the docker-compose.yml to provide some hosts:

    .. code-block:: py

        >>> hosts = DockerCompose(project_name='myproject')
    """

    def __init__(self, project_name=None, compose_file=None):
        self.project_name = project_name
        self.compose_file = compose_file
        self.args = []
        if self.project_name:
            self.args.extend(['--project-name', self.project_name])
        if self.compose_file:
            self.args.extend(['--file', self.compose_file])
        super().__init__()

    async def boot(self):
        """launch ``docker-compose up`` and setup all containers"""
        cmd = [sys.executable, '-m', 'compose'] + self.args + ['up', '-d']
        subprocess.check_call(cmd)
        cmd = [sys.executable, '-m', 'compose'] + self.args + ['ps']
        stdout = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT)
        stdout = stdout.decode('utf8')
        for line in stdout.split('\n')[2:]:
            if line.strip():
                name = line.split()[0]
                self[name] = DockerContainer(hostname=name)
        if self:
            await asyncio.wait([wait_for_boot(h) for h in self.values()])

    async def destroy(self):
        """launch ``docker-compose down``"""
        cmd = [sys.executable, '-m', 'compose'] + self.args + ['down']
        p = subprocess.Popen(cmd)
        p.wait()
        for host in self.values():
            host.vars['destroyed'] = True
        return True


def update_image(base_image):
    container = DockerContainer(
        hostname='nuka',
        image=base_image,
        command=['bash', '-c', 'while true; do sleep 1000000000000; done'],
        )
    nuka.run(wait_for_boot(host=container))
    image, tag = base_image.split(':', 1)
    container.cli.commit(
        container.container_id, repository='nuka_' + image, tag=tag)
    return container


def clean_images():
    cli = docker_py.Client()
    for image in cli.images():
        if image['RepoTags'] == ['<none>:<none>']:
            print('Removing {Id}'.format(**image))
            cli.remove_image(image['Id'])
