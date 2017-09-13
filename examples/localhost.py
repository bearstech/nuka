import nuka
from nuka.tasks import shell
from nuka.hosts import LocalHost

host = LocalHost()


async def ls(host):
    print(await shell.command(['ls', '/']))

nuka.run(
    ls(host),
)
