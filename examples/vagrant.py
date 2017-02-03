from nuka.hosts import Vagrant
from nuka.tasks import shell
import nuka

host = Vagrant()


async def my_tasks(host):
    await shell.command('whoami')

nuka.run(my_tasks(host))
