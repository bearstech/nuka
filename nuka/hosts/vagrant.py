# -*- coding: utf-8 -*-
import subprocess
import sys

from nuka.hosts.base import Host
import nuka


class Vagrant(Host):
    """A host configured using ``vagrant ssh-config``"""

    def __init__(self, **kwargs):
        kwargs['hostname'] = 'default'
        super().__init__(**kwargs)
        self.port = None
        self.config_file = '/tmp/nuka_vagrant'
        try:
            subprocess.check_call(
                'vagrant ssh-config > ' + self.config_file,
                shell=True)
        except subprocess.CalledProcessError:
            print('VM is down. Please run vagrant up...')
            sys.exit(1)

    def wraps_command_line(self, cmd, **kwargs):
        ssh_user = kwargs.get('switch_ssh_user')
        if ssh_user is None:
            # we use the main user account
            switch_user = kwargs.get('switch_user') or 'root'
            if switch_user != 'root':
                if switch_user != self.vars['user']:
                    # we have to use sudo
                    args = (switch_user, cmd)
                    if self.use_sudo:
                        cmd = '{sudo} -u {0} {1}'.format(*args, **nuka.config)
                    else:
                        cmd = '{su} -c "{1}" {0}'.format(*args, **nuka.config)
            elif self.use_sudo:
                cmd = '{sudo} {0}'.format(cmd, **nuka.config)

        if ssh_user is None:
            ssh_user = self.vars['user']

        ssh_cmd = ['ssh', '-F', self.config_file]
        ssh_cmd.extend(nuka.config['ssh']['options'] + ['-l', ssh_user])
        if self.port:
            ssh_cmd.extend(['-p', self.port])
        ssh_cmd.extend([self.hostname, cmd])
        return ssh_cmd
