#!../bin/python
from nuka.hosts import DockerCompose
from nuka.tasks import shell
import nuka

hosts = DockerCompose(project_name='myproject')
nuka.run(hosts.boot())

host = hosts['myproject_debian_stretch_1']


async def my_tasks(host):
    await shell.shell('whoami')

nuka.run(my_tasks(host))
