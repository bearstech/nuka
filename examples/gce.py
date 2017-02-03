#!../bin/python
# -*- coding: utf-8 -*-
import nuka
from nuka.hosts import Cloud
from nuka.tasks import shell

nuka.config['gce'] = {
    'driver': '~/.gce/nuka.json',
    'user': 'gawel',
    'create_node_args': {
        'size': 'f1-micro',
        'image': 'debian-8-jessie-v20161215',
        'location': 'europe-west1-d',
        'ex_tags': ['nuka'],
        'ex_disk_auto_delete': True,
        'ex_service_accounts': [{
            'scopes': [
                'https://www.googleapis.com/auth/cloud.useraccounts.readonly',
                'https://www.googleapis.com/auth/devstorage.read_only',
                'https://www.googleapis.com/auth/logging.write',
                'https://www.googleapis.com/auth/monitoring.write',
                'https://www.googleapis.com/auth/service.management.readonly',
                'https://www.googleapis.com/auth/servicecontrol'
             ],
        }]
    },
}

nuka.config['ssh'].update({
    'extra_options': ['-C', '-oStrictHostKeyChecking=no'],
    'keysfile': '~/.ssh/authorized_keys',
})


cloud = Cloud('gce')
host = cloud.get_or_create_node('myhost')


async def my_tasks(host):
    await shell.command(['ls'])

nuka.cli.add_argument('--destroy', action='store_true', default=False)
nuka.cli.parse_args()

if nuka.cli.args.destroy:
    nuka.run(cloud.destroy())
else:
    nuka.run(my_tasks(host))
