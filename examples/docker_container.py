# -*- coding: utf-8 -*-
from nuka.hosts import DockerContainer
from nuka.tasks import shell
import nuka

host = DockerContainer(hostname='debian', image='bearstech/nukai')


async def my_tasks(host):
    await shell.shell('whoami')

nuka.run(my_tasks(host))
