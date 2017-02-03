# -*- coding: utf-8 -*-
import nuka
from nuka.hosts import DockerContainer
from nuka.tasks import shell

host = DockerContainer(
    hostname='debian_jessie',
    image='debian:jessie',
    command=['bash', '-c', 'while true; do sleep 1000000000000; done'],
)


async def sleep(host):
    await shell.command(['sleep', '5'], watch=1)


nuka.run(sleep(host))
