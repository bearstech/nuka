#!../bin/python
import nuka
from nuka.hosts import DockerContainer
from nuka.tasks import apt


async def install(host):
    res = await apt.update()
    print(res.res)
    res = await apt.install(['procps', 'varnish', 'nginx'])
    print(res.res)


nuka.run(install(DockerContainer('apt')))
