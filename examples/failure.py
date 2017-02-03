# -*- coding: utf-8 -*-
import nuka
from nuka.hosts import DockerContainer
from nuka.tasks import shell

host = DockerContainer(hostname='nukai')

e = nuka.Event('event')


@nuka.cancel_on_error(e)
async def fail(host):
    await shell.command(['sleep', '2'])
    raise AttributeError()
    await shell.command(['sleep', '1'])
    e.release()


async def wait(host):
    await nuka.wait(e)
    await shell.command(['sleep', '2'])


async def not_wait(host):
    await shell.command(['sleep', '1'])
    await shell.command(['rm', '/usr'])
    await shell.command(['sleep', '3'])

nuka.run(
    fail(host),
    wait(host),
    not_wait(host),
)
nuka.run(host.destroy())
