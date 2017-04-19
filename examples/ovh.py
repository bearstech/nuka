#!../bin/python
# -*- coding: utf-8 -*-
import nuka
from nuka.hosts import Cloud
from nuka.tasks import shell

nuka.config['openstack'] = {
    'driver': '~/.ovh/nuka.json',
    'user': 'debian',
    'create_node_args': {
        'flavor': 's1-2',
        'image': 'Debian 8',
        'key_name': 'gawel',
    },
}

nuka.config['ssh'].update({
    'extra_options': ['-C', '-oStrictHostKeyChecking=no'],
    'keysfile': '~/.ssh/authorized_keys',
})


cloud = Cloud('openstack')
host = cloud.get_or_create_node('myhost')


async def my_tasks(host):
    await shell.command(['ls'])

nuka.cli.add_argument('--destroy', action='store_true', default=False)
nuka.cli.parse_args()

if nuka.cli.args.destroy:
    nuka.run(cloud.destroy())
else:
    nuka.run(my_tasks(host))
