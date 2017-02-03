#!../bin/python
from os.path import (join, basename)
import tempfile

import nuka
from nuka.hosts import DockerContainer
from nuka.tasks import (apt, user, virtualenv, shell, http, file)

nuka.config['templates'].append('/tmp')

kinto = DockerContainer('kinto')

WSGI_FILE = 'https://raw.githubusercontent.com/Kinto/kinto/master/app.wsgi'


async def install_kinto(host):
    kinto_user = user.create_www_user('kinto')
    await nuka.wait(
        kinto_user,
        apt.install([
            'apache2', 'libapache2-mod-wsgi',
            'build-essential', 'libffi-dev', 'libssl-dev',
            'python3-dev', 'redis-server'
        ], update_cache=3600))

    with open('/tmp/requirements.txt', 'wb') as fd:
        fd.write(b'kinto\n')
        fd.flush()
        await virtualenv.virtualenv(
            dst=kinto_user.home,
            requirements=fd.name,
            switch_user='kinto')

    binary = join(kinto_user.home, 'bin', 'kinto')
    config = join(kinto_user.home, 'config', 'kinto.ini')

    if not await file.exists(config):
        await shell.command([binary, 'init', '--backend=redis'],
                            switch_user='kinto')
    await shell.command([binary, 'migrate'],
                        switch_user='kinto')

    if not await file.exists('app.wsgi', switch_user='kinto'):
        await http.fetch(
            src=WSGI_FILE,
            dst='app.wsgi', switch_user='kinto')

    with tempfile.NamedTemporaryFile(suffix='.j2') as fd:
        fd.write(b'''
ServerName kinto.example.com

WSGIScriptAlias /         {{kinto_user.home}}/app.wsgi
WSGIPythonPath            {{kinto_user.home}}
SetEnv          KINTO_INI {{kinto_config}}

<Directory {{kinto_user.home}}>
  <Files app.wsgi>
    Require all granted
  </Files>
</Directory>
''')
        fd.flush()
        conf = await file.put([dict(
            src=basename(fd.name),
            dst='/etc/apache2/sites-available/kinto.conf')],
            ctx=dict(kinto_user=kinto_user, kinto_config=config))

    if conf.changed:
        await shell.command(['a2ensite', 'kinto.conf'])


nuka.run(install_kinto(kinto))
