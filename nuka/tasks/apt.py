# -*- coding: utf-8 -*-
"""
apt related tasks
"""
import os
import time
import codecs

from nuka.tasks import http
from nuka.task import Task

import logging as log

GPG_HEADER = b'-----BEGIN PGP PUBLIC KEY BLOCK-----'


def apt_watcher(delay, fd):
    """watcher for apt using APT::Status-Fd"""
    def watcher(task, process):
        start = time.time()
        inc = delay
        new_line = last_sent = None
        while True:
            if task.is_alive(process):
                value = time.time() - start
                if value > inc:
                    line = fd.readline()
                    while line:
                        if line.startswith(('dlstatus:', 'pmstatus:')):
                            line = line.strip()
                            new_line = line
                        line = fd.readline()
                    if new_line != last_sent:
                        last_sent = new_line
                        inc += delay
                        task.send_progress(new_line.split(':', 3)[-1])
                yield
            else:
                # process is dead
                yield
    return watcher


class source(Task):
    """add an apt source"""

    def __init__(self, name=None, src=None, key=None, update=True, **kwargs):
        super(source, self).__init__(name=name, src=src, key=key,
                                     update=update, **kwargs)

    def add_key(self, key):
        if isinstance(key, str):
            if key.startswith('http'):
                res = http.fetch(src=key).do()
                dst = res['dst']
            else:
                dst = key
            with open(dst, 'rb') as fd:
                data = fd.read()
            fname = '/etc/apt/trusted.gpg.d/{0}.gpg'.format(self.args['name'])
            if GPG_HEADER in data:
                self.sh('gpg --dearmor > {0}'.format(fname),
                        shell=True, stdin=data)
            else:
                with open(fname, 'wb') as fd:
                    fd.write(data)
        elif isinstance(key, tuple):
            keyserver, keyid = key
            self.sh([
                'apt-key', 'adv',
                '--keyserver', keyserver,
                '--recv-keys', keyid])

    def do(self):
        name = self.args['name']
        src = self.args['src'].strip()
        src += '\n'
        dst = os.path.join('/etc/apt/sources.list.d', name + '.list')
        changed = True
        if os.path.isfile(dst):
            with codecs.open(dst, 'r', 'utf8') as fd:
                if fd.read() == src:
                    changed = False
        if changed:
            key = self.args['key']
            if key is not None:
                self.add_key(key)
            with codecs.open(dst, 'w', 'utf8') as fd:
                fd.write(src)
            if self.args['update']:
                cmd = [
                    'apt-get', 'update',
                    '-oDir::Etc::sourcelist=' + dst,
                    '-oDir::Etc::sourceparts=-',
                    '-oAPT::Get::List-Cleanup=0'
                ]
                self.sh(cmd)
        return dict(rc=0, changed=changed)

    def diff(self):
        name = self.args['name']
        src = self.args['src'].strip()
        src += '\n'
        dst = os.path.join('/etc/apt/sources.list.d', name + '.list')
        if os.path.isfile(dst):
            with codecs.open(dst, 'r', 'utf8') as fd:
                old_data = fd.read()
        else:
            old_data = ''
        if old_data != src:
            diff = self.texts_diff(old_data, src, fromfile=dst)
        else:
            diff = u''
        return dict(rc=0, diff=diff)


class update(Task):
    """apt get update"""

    timestamp_file = '/root/.last-apt-get-update'

    def __init__(self, cache=None, **kwargs):
        kwargs.setdefault('name', '')
        kwargs.update(cache=cache)
        super(update, self).__init__(**kwargs)

    def do(self):
        cache = self.args['cache']
        timestamp_file = self.args.get('timestamp_file', self.timestamp_file)
        if cache:
            try:
                mtime = os.path.getmtime(timestamp_file)
            except OSError:
                need_update = True
            else:
                need_update = time.time() > mtime + cache
        else:
            need_update = True

        if need_update:
            kwargs = {}
            args = ['apt-get', '--force-yes', '-y', '--fix-missing']
            watch = self.args.get('watch')
            if watch:
                r, w = os.pipe2(os.O_NONBLOCK)
                kwargs['stdout'] = os.fdopen(w)
                kwargs['watcher'] = apt_watcher(watch, os.fdopen(r))
                kwargs['short_args'] = ['apt-get', 'update']
                args.extend(['-oAPT::Status-Fd=1', 'update'])
                res = self.sh(args, **kwargs)
                res['stdout'] = ''
            else:
                res = self.sh(args + ['update'], **kwargs)
            if cache:
                with codecs.open(timestamp_file, 'w', 'utf8') as fd:
                    fd.write(str(time.time()))
            res['changed'] = True
        else:
            res = dict(rc=0, changed=False)
        return res


class list(Task):

    ignore_errors = True

    def __init__(self, update_cache=None, **kwargs):
        kwargs.update(update_cache=update_cache)
        super(list, self).__init__(**kwargs)

    def do(self):
        update_cache = self.args.get('update_cache')
        if update_cache is not None:
            res = update(cache=update_cache).do()

        res = self.sh(['apt-get', 'upgrade', '-qq', '-s'], check=False)

        return res


class search(Task):

    def __init__(self, packages, **kwargs):
        kwargs.setdefault('name', ', '.join(packages or []))
        kwargs.update(packages=packages)
        super(search, self).__init__(**kwargs)

    def do(self):
        query = self.sh(['dpkg-query',
                         '-f', "'${Package}#${Status}#${Version}~\n'",
                         '-W'] + self.args['packages'],
                        check=False)
        if query['rc'] == 1:
            # not an error for dpkg-query
            query['rc'] = 0
        return query


class upgrade(Task):

    ignore_errors = True

    def __init__(self, packages=None, debconf=None,
                 debian_frontend='noninteractive', **kwargs):
        kwargs.setdefault('name', ', '.join(packages or []))
        kwargs.update(packages=packages, debconf=debconf,
                      debian_frontend=debian_frontend)
        super(upgrade, self).__init__(**kwargs)

    def do(self):
        self.sh(['rm', '/var/lib/apt/lists/partial/*'], check=False)
        env = {}
        for k in ('debian_priority', 'debian_frontend'):
            v = self.args.get(k)
            if v:
                env[k.upper()] = v
        kwargs = {'env': env}
        #  no specific package :
        if not self.args['packages']:
            res = self.sh([
                'apt-get', '-qq', '-y',
                '-oDpkg::Options::=--force-confdef',
                '-oDpkg::Options::=--force-confold', 'upgrade'
                ], check=False, **kwargs)
            return res
        else:
            to_upgrade = []
            miss_packages = []
            #  we check for all package it they are endeed installed
            for package in self.args['packages']:
                is_present = self.sh(['dpkg-query',
                                      '-f', '\'${Status}\'',
                                      '-W', package],
                                     check=False)
                log.warn(is_present['stdout'])
                if is_present['rc'] or \
                   " installed" not in is_present['stdout']:
                    #  we don't want installed package
                    miss_packages.append(package)
                    continue
                to_upgrade.append(package)
            if to_upgrade:
                cmd = ['apt-get', '-qq', '-y',
                       '-oDpkg::Options::=--force-confdef',
                       '-oDpkg::Options::=--force-confold',
                       '--only-upgrade', 'install'
                       ] + to_upgrade
                res = self.sh(cmd, check=False, **kwargs)
            else:
                res = dict(rc=0, stdout='no upgrade')
                res['changed'] = False
            res['miss_packages'] = miss_packages
            res['packages'] = to_upgrade
            return res


class debconf_set_selections(Task):
    """debconf-set-selections"""

    diff = False

    def __init__(self, selections=None, **kwargs):
        super(debconf_set_selections, self).__init__(
            selections=selections, **kwargs)

    def do(self):
        selections = []
        for selection in self.args['selections']:
            selections.append(' '.join(selection))
        res = self.sh('debconf-set-selections',
                      stdin='\n'.join(selections), check=True)
        return res


class install(Task):
    """apt get install"""

    debconf = {
        'mysql-server': (
            ['mysql-server/root_password', 'password'],
            ['mysql-server/root_password_again', 'password'],
        ),
    }

    def __init__(self, packages=None, debconf=None,
                 debian_frontend='noninteractive', debian_priority=None,
                 update_cache=None, install_recommends=False, **kwargs):
        kwargs.setdefault('name', ', '.join(packages or []))
        kwargs.update(packages=packages, debconf=debconf,
                      debian_priority=debian_priority,
                      debian_frontend=debian_frontend,
                      update_cache=update_cache,
                      install_recommends=install_recommends,
                      )
        super(install, self).__init__(**kwargs)

    def get_packages_list(self, packages):
        splited = dict([(p.split('/', 1)[0], p) for p in packages])
        cmd = ['apt-cache', 'policy'] + [k for k in splited.keys()]
        res = self.sh(cmd, check=False)
        package = source = None
        packages = {}
        for line in res['stdout'].split('\n'):
            sline = line.strip()
            if not line.startswith(' '):
                if package:
                    packages[package['name']] = package
                package = {'name': line.strip()[:-1]}
                source = None
            elif sline.startswith(('Installed:', 'Candidate:')):
                key, value = sline.split(':', 1)
                value = value.strip()
                if value.lower() == '(none)':
                    value = False
                package[key.lower()] = value
            elif sline.startswith('***'):
                source = sline.split()[-1] + ' '
                if source.startswith('0'):
                    package['source'] = splited[package['name']]
                    source = None
            elif source and sline.startswith(source):
                package['source'] = sline
                source = None
        installed = []
        for name, fullname in splited.items():
            package = packages.get(name, {})
            if name in packages:
                if package.get('installed'):
                    if '/' in fullname:
                        name, source = fullname.split('/', 1)
                        if source in package.get('source', ''):
                            installed.append(fullname)
                    else:
                        installed.append(fullname)
        return installed

    def do(self):
        """install packages"""
        packages = self.args['packages']
        debconf = self.args['debconf']
        if not packages:
            return dict(rc=1, stderr='no packages provided')
        installed = self.get_packages_list(packages)
        to_install = [p for p in packages if p not in installed]
        if to_install:
            watch = self.args.get('watch')
            update_cache = self.args.get('update_cache')
            if update_cache is not None:
                update(cache=update_cache, watch=watch).do()
            if debconf:
                for p in to_install:
                    conf = debconf.get(p, [])
                    for i, c in enumerate(self.debconf.get(p, [])):
                        if isinstance(conf, list):
                            v = conf[i]
                        else:
                            v = conf
                        stdin = ' '.join([p] + c + [v])
                        self.sh(['debconf-set-selections'], stdin=stdin)
            env = {}
            for k in ('debian_priority', 'debian_frontend'):
                v = self.args.get(k)
                if v:
                    env[k.upper()] = v
            kwargs = {'env': env}
            args = ['apt-get', 'install', '-qqy',
                    '-oDpkg::Options::=--force-confold']
            if not self.args.get('install_recommends'):
                args.append('--no-install-recommends')
            if watch:
                r, w = os.pipe2(os.O_NONBLOCK)
                kwargs['stdout'] = os.fdopen(w)
                kwargs['watcher'] = apt_watcher(watch, os.fdopen(r))
                kwargs['short_args'] = ['apt-get', 'install']
                args.extend(['-oAPT::Status-Fd=1'] + packages)
                res = self.sh(args, **kwargs)
                res['stdout'] = ''
            else:
                res = self.sh(args + packages, **kwargs)
        else:
            res = dict(rc=0)
        res['changed'] = to_install
        return res

    def diff(self):
        packages = self.args['packages']
        installed = self.get_packages_list(packages)
        to_install = [p for p in packages if p not in installed]
        installed = [p + '\n' for p in sorted(set(installed))]
        packages = [p + '\n' for p in sorted(set(packages))]
        diff = self.lists_diff(installed, packages)
        return dict(rc=0, diff=diff, changed=to_install)
