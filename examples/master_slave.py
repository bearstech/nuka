# -*- coding: utf-8 -*-
import nuka
from nuka.hosts import DockerContainer

master = DockerContainer('master')
slave = DockerContainer('slave')

e = nuka.Event('master_ready')


async def my_tasks(host):
    if host is slave:
        await nuka.wait(e)
        host.log.warn('starting slave')
    else:
        host.log.warn('master ready')
        e.release()

nuka.run(
    my_tasks(slave),
    my_tasks(master),
)
