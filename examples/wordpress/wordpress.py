#!../../bin/python
# -*- coding: utf-8 -*-
import nuka
from nuka.hosts import (DockerCompose, Cloud, Provider)
from nuka.tasks import (apt, shell, file, user, archive, service)

import mysql


nuka.cli.add_argument('--gce', action='store_true', default=False)
nuka.cli.add_argument('--ovh', action='store_true', default=False)
nuka.cli.add_argument('--destroy', action='store_true', default=False)
nuka.cli.parse_args()


if nuka.cli.args.ovh:
    all_hosts = Cloud(Provider.OPENSTACK).from_compose()
elif nuka.cli.args.gce:
    all_hosts = Cloud(Provider.GCE).from_compose()
else:
    all_hosts = DockerCompose()
    if not nuka.cli.args.destroy:
        nuka.run(all_hosts.boot())


nuka.config['all_hosts'] = all_hosts
master = all_hosts['wordpress_master_1']
slave = all_hosts['wordpress_slave_1']
web = all_hosts['wordpress_web_1']


mysql_password = nuka.utils.secret('dsmfk;m#lkf!(').next()
db_password = nuka.utils.secret('q,sddsmfk;m#lkf!(').next()


async def install_wordpress(host):
    await apt.install(['apache2', 'libapache2-mod-php5',
                       'php5-mysql', 'mysql-client'], update_cache=3600)
    u = await user.create_www_user('wp')
    wp_dir = u.home + '/wordpress'
    await archive.untar(src='https://wordpress.org/latest.tar.gz',
                        dst=u.home,
                        switch_user=u.username)
    await file.put(
        [dict(src='wordpress/wp-config.php.j2',
              dst=wp_dir + '/wp-config.php')],
        ctx=dict(database='wp', user='wp',
                 password=db_password,
                 hostname=master.private_ip,
                 secret=nuka.utils.secret('dsoi,mfjqm'),
                 debug=False,
                 ),
        switch_user=u.username)
    await file.put(
        [dict(src='wordpress/apache.conf.j2',
              dst='/etc/apache2/sites-available/wp.conf')],
        ctx=dict(document_root=wp_dir))

    await nuka.wait(mysql.mysql_ready)

    await shell.command(['a2dissite', '000-default.conf'])
    await shell.command(['a2ensite', 'wp'])
    await service.restart('apache2')

    host.log('URL: http://' + host.hostname)


if nuka.cli.args.destroy:
    nuka.run(all_hosts.destroy())
else:
    nuka.run(
        mysql.install_master(
            master, mysql_password,
            db_name='wp', db_user='wp', db_password=db_password,
            slave=slave),
        mysql.install_slave(slave, mysql_password),
        install_wordpress(web),
    )
