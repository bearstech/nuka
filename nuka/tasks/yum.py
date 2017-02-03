"""
yum related tasks
"""
import os
import time
import codecs

from nuka.task import Task


class update(Task):
    """yum update"""

    timestamp_file = '/root/.last-yum-update'

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
                need_update = time.time() < mtime + cache
        else:
            need_update = True

        if need_update:
            res = self.sh(['yum', 'update', '-q', '-y'])
            if cache:
                with codecs.open(timestamp_file, 'w', 'utf8') as fd:
                    fd.write(str(time.time()))
            res['changed'] = True
        else:
            res = dict(rc=0, changed=False)
        return res


class install(Task):
    """yum install"""

    def __init__(self, packages=None, update_cache=None, **kwargs):
        kwargs.setdefault('name', ', '.join(packages or []))
        kwargs.update(packages=packages, update_cache=update_cache)
        super(install, self).__init__(**kwargs)

    def pkg_list(self, packages):
        installed = []
        res = self.sh(['yum', '-q', 'list', 'installed'] + (packages or []),
                      check=False)
        in_list = False
        for line in res['stdout'].split('\n'):
            if not line:
                continue
            elif line.lower().startswith('installed packages'):
                in_list = True
                continue
            elif not in_list:
                continue
            line = line.split()
            package = line[0]
            package = package.split('.', 1)[0]
            installed.append(package)
        return installed

    def do(self):
        """install packages"""
        packages = self.args['packages']
        if not packages:
            return dict(rc=1, stderr='no packages provided')
        installed = self.pkg_list(packages)
        to_install = [p for p in packages if p not in installed]
        if to_install:
            update_cache = self.args.get('update_cache')
            if update_cache is not None:
                update(cache=update_cache).do()
            res = self.sh(['yum', 'install', '-q', '-y'] + packages)
        else:
            res = dict(rc=0)
        res['changed'] = to_install
        return res

    def diff(self):
        packages = self.args['packages']
        installed = self.pkg_list(packages)
        installed = [p + '\n' for p in sorted(installed)]
        packages = [p + '\n' for p in sorted(packages)]
        diff = self.lists_diff(installed, packages)
        return dict(rc=0, diff=diff, packages=packages)
