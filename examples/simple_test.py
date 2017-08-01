# -*- coding: utf-8 -*-
import nuka
from nuka.hosts import DockerContainer
from nuka.hosts import Host
from nuka.tasks import shell

nuka.config['ssh']['extra_options'] = ['-C', '-oStrictHostKeyChecking=yes']

host1 = DockerContainer(hostname='debian_jessie')
host2 = Host(hostname='unkownhost')


async def echo():
    print('echo')


async def ls(host):
    await shell.command(['ls'])


print(nuka.run(ls(host2)))
print(nuka.run(echo(), ls(host1), ls(host2)))
