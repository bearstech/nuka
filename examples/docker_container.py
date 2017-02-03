# -*- coding: utf-8 -*-
from nuka.hosts import DockerContainer
from nuka.tasks import shell
import nuka

host = DockerContainer(
    hostname='debian_jessie',
    image='debian:jessie',
    command=['bash', '-c', 'while true; do sleep 1000000000000; done'],
)


async def f(host):
    await shell.shell('whoami')

nuka.run(f(host))
