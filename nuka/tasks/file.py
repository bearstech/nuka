# -*- coding: utf-8 -*-
"""
file related tasks
"""
from nuka.task import Task
from nuka import utils
import codecs
import stat
import re
import os


class exists(Task):
    """return True if a path exists"""

    ignore_errors = True

    def __init__(self, dst=None, **kwargs):
        kwargs.setdefault('name', dst)
        kwargs.setdefault('dst', dst)
        super(exists, self).__init__(**kwargs)

    def do(self):
        dst = self.args['dst']
        if os.path.exists(dst):
            return dict(rc=0, dst=dst, changed=False)
        return dict(rc=1, dst=dst)

    def diff(self):
        dst = self.args['dst']
        if os.path.exists(dst):
            return dict(rc=0, dst=dst, diff='', changed=False)
        diff = self.texts_diff('', dst)
        return dict(rc=1, dst=dst, diff=diff)


class mkdir(Task):
    """create a directory"""

    def __init__(self, dst=None, mod=None, **kwargs):
        kwargs.setdefault('name', dst)
        kwargs.update(dst=dst, mod=mod)
        super(mkdir, self).__init__(**kwargs)

    def do(self):
        dst = self.args['dst']
        mod = self.args['mod']
        res = utils.makedirs(dst, mod=mod)
        res.update(rc=0, dst=dst)
        return res

    def diff(self):
        dst = self.args['dst']
        diff = ''
        if not os.path.exists(dst):
            res = self.lists_diff([], [dst + '\n'], fromfile=dst)
            diff = u''.join(res) + u'\n'
        return dict(rc=0, diff=diff)


class rm(Task):
    """rm a file or directory"""

    def __init__(self, dst=None, **kwargs):
        kwargs.setdefault('name', dst)
        kwargs.setdefault('dst', dst)
        super(rm, self).__init__(**kwargs)

    def do(self):
        dst = self.args['dst']
        if os.path.exists(dst):
            try:
                if os.path.isdir(dst):
                    import shutil
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)
                return dict(rc=0)
            except:
                exc = self.format_exception()
                return dict(rc=1, exc=exc)
        return dict(rc=1)

    def diff(self):
        dst = self.args['dst']
        diff = ''
        if os.path.exists(dst):
            res = self.lists_diff([dst + '\n'], [], fromfile=dst)
            diff = u''.join(res) + u'\n'
        return dict(rc=0, diff=diff)


class chmod(Task):
    """apply chmod to dst"""

    def __init__(self, dst=None, mod='644', **kwargs):
        kwargs.setdefault('name', dst)
        super(chmod, self).__init__(dst=dst, mod=mod, **kwargs)

    def do(self):
        dst = self.args['dst']
        mod = self.args['mod']
        utils.chmod(dst, mod)
        return dict(rc=0, dst=dst, mod=mod)


class put(Task):
    """put files on the remote host"""

    def __init__(self, files=None, **kwargs):
        kwargs.setdefault('name', [f['dst'] for f in files or []])
        super(put, self).__init__(files=files, **kwargs)

    def pre_process(self):
        for fd in self.args['files']:
            if 'src' in fd:
                src = fd['src']
                if src.startswith('~/'):
                    fd['src'] = os.path.expanduser(src)
                if src.endswith('.j2'):
                    self.render_template(fd)
                else:
                    self.render_file(fd)
            elif 'data' not in fd:
                raise RuntimeError('cant get content for fd {0}'.format(fd))

    def do(self):
        files = self.args['files'] or []
        files_changed = []
        for fd in files:
            dst = fd['dst']
            if dst.startswith('~/'):
                dst = fd['dst'] = os.path.expanduser(dst)
            data = fd['data']
            if os.path.exists(dst):
                with codecs.open(dst, 'rb', 'utf8') as fd_:
                    if data != fd_.read():
                        files_changed.append(dst)
            else:
                files_changed.append(dst)
            with codecs.open(dst, 'wb', 'utf8') as fd_:
                fd_.write(data)
            mod = fd.get('mod')
            if mod is None and fd.get('executable'):
                st = os.stat(dst)
                mod = st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
            if mod is not None:
                utils.chmod(dst, mod)
        return dict(rc=0, changed=files_changed)

    def diff(self):
        diff = ''
        files = self.args['files'] or []
        for fd in files:
            dst = fd['dst']
            new_text = fd['data']
            if not os.path.isfile(dst):
                old_text = ''
            else:
                with codecs.open(dst, 'rb', 'utf8') as fd_:
                    old_text = fd_.read()
            diff += self.texts_diff(old_text, new_text, fromfile=dst)
        return dict(rc=0, diff=diff)


class scripts(put):
    """put and execute scripts on the remote host"""

    def do(self):
        files = self.args['files'] or []
        for f in files:
            f['executable'] = True
        super(scripts, self).do()
        for f in files:
            res = self.sh(f['dst'])
        return res


class cat(Task):
    """cat a file"""

    def __init__(self, src=None, **kwargs):
        kwargs.setdefault('name', src)
        super(cat, self).__init__(src=src, **kwargs)

    def do(self):
        src = self.args['src']
        with codecs.open(src, 'rb', 'utf8') as fd:
            res = dict(rc=0, content=fd.read())
        return res


class update(Task):
    """update a file"""

    def __init__(self, dst=None, replaces=None, appends=None, **kwargs):
        kwargs.setdefault('name', dst)
        super(update, self).__init__(
            dst=dst, replaces=replaces, appends=appends, **kwargs)

    def pre_process(self):
        for regex, value in self.args['replaces']:
            re.compile(regex)

    def update(self, data):
        for regex, value in self.args['replaces'] or []:
            data = re.sub(regex, value, data, flags=re.MULTILINE)
        lines = data.splitlines(1)
        for after, value in self.args['appends'] or []:
            value += '\n'
            if value not in lines:
                if after == 'EOF':
                    lines.append(value)
                else:
                    for i, line in enumerate(lines):
                        if re.match(after, line):
                            lines[i + 1:i + 1] = [value]
        return ''.join(lines)

    def do(self):
        dst = self.args['dst']
        with codecs.open(dst, 'r', 'utf8') as fd:
            old_data = data = fd.read()
        data = self.update(data)
        changed = old_data != data
        if changed:
            with codecs.open(dst, 'w', 'utf8') as fd:
                fd.write(data)
        return dict(rc=0, changed=changed)

    def diff(self, dst=None, **kwargs):
        dst = self.args['dst']
        with codecs.open(dst, 'r', 'utf8') as fd:
            old_data = data = fd.read()
        data = self.update(data)
        if old_data != data:
            diff = self.texts_diff(old_data, data, fromfile=dst)
        else:
            diff = u''
        return dict(rc=0, diff=diff)
