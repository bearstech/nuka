#!/usr/bin/env python3.5
import nuka
from nuka.hosts import DockerContainer
from nuka.tasks import (shell, file)

# setup a docker container using the default image
host = DockerContainer('mycontainer')


async def do_something(host):

    # we just echoing something using the shell.command task
    await shell.command(['echo', 'it works'], host=host)

    # if no host is provided, then a var named `host` is searched
    # from the stack. Mean that this will works to
    await shell.command(['echo', 'it works too'])


async def do_something_else(host):

    # log /etc/resolv.conf content
    res = await file.cat('/etc/resolv.conf')
    host.log.info(res.content)


# those coroutines will run in parallell
nuka.run(
    do_something(host),
    do_something_else(host),
)
