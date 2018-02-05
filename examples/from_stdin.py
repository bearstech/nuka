'''
Usage: cat hostlist | python from_stdin.py
'''
import nuka
from nuka.tasks import file
from nuka.hosts import Host


async def do(host):
    res = await file.cat('/etc/debian_version')
    print(res.content)

nuka.run_all(do, *Host.from_stdin())
