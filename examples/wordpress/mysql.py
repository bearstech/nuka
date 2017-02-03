# -*- coding: utf-8 -*-
import nuka
from nuka.tasks import apt
from nuka.tasks import mysql
from nuka.tasks import file
from nuka.tasks import service


mysql_ready = nuka.Event('mysql_ready')


async def install_mysql(host, mysql_password):
    await apt.install(
            debconf={'mysql-server': mysql_password},
            packages=['mysql-server'], update_cache=3600)
    await service.start('mysql')
    await mysql.my_cnf(password=mysql_password)


@nuka.cancel_on_error(mysql_ready)
async def install_master(
        host, mysql_password,
        db_name=None, db_user=None, db_password=None,
        slave=None):
    await install_mysql(host, mysql_password)
    conf = await file.update(
        dst='/etc/mysql/my.cnf',
        replaces=[
            ('^bind-address.+=.+\S+$',
             'bind-address = ' + host.private_ip),
            ('^\#server-id', 'server-id'),
            ('^\#*log_bin', 'log_bin'),
            ('^expire_logs_days.+=.+\S+$', 'expire_logs_days = 1'),
            ('^\#*binlog_do_db.+=.+\S+$', 'binlog_do_db = wp'),
        ],
        appends=[
            ('^binlog_do_db =', 'binlog_format = ROW'),
            ('^binlog_format =', 'transaction-isolation = READ-COMMITTED'),
        ])
    if conf.changed:
        await service.restart('mysql')
    if db_name:
        await mysql.create_db(name=db_name, user=db_user, password=db_password)
    if slave is not None:
        await mysql.execute(
            name='GRANT REPLICATION TO {0}'.format(slave),
            sql='''
                GRANT REPLICATION SLAVE ON *.*
                TO 'replica'@'{0}' IDENTIFIED BY '{1}';
                FLUSH PRIVILEGES;'''.format(slave.private_ip, mysql_password))
    mysql_ready.release()


async def install_slave(host, mysql_password):
    await install_mysql(host, mysql_password)
    conf = await file.update(
        dst='/etc/mysql/my.cnf',
        replaces=[
            ('^\#server-id.+=.+$', 'server-id = 2'),
        ],
        appends=[
            ('^server-id', 'relay_log_space_limit = 5G'),
            ('^relay_log_space_limit', 'replicate-do-db = wp'),
        ])
    if conf.changed:
        await nuka.wait(mysql_ready)
        await service.restart('mysql')
