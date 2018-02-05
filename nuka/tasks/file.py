# -*- coding: utf-8 -*-
"""
file related tasks
"""
from nuka.task import Task
from nuka import utils
import logging
import codecs
import stat
import glob
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

    def __init__(self, dst=None, mod=None, own=None, **kwargs):
        kwargs.setdefault('name', dst)
        kwargs.update(dst=dst, mod=mod, own=None)
        super(mkdir, self).__init__(**kwargs)

    def do(self):
        dst = self.args['dst']
        mod = self.args['mod']
        own = self.args['mod']
        res = utils.makedirs(dst, mod=mod, own=own)
        res.update(rc=0, dst=dst)
        return res

    def diff(self):
        dst = self.args['dst']
        diff = ''
        if not os.path.exists(dst):
            res = self.lists_diff([], [dst + '\n'], fromfile=dst)
            diff = u''.join(res) + u'\n'
        return dict(rc=0, diff=diff, dst=dst)


class mkdirs(Task):
    """create directories"""

    def __init__(self, directories=None, **kwargs):
        kwargs.setdefault('name', ', '.join([d['dst'] for d in directories]))
        super(mkdirs, self).__init__(directories=directories, **kwargs)

    def do(self):
        res = dict(rc=0, changed=[])
        for d in self.args['directories']:
            dst = d.pop('dst')
            r = utils.makedirs(dst, **d)
            if r['changed']:
                res['changed'].append(dst)
        return res

    def diff(self):
        res = dict(rc=0, diff='', changed=[])
        for d in self.args['directories']:
            dst = d.pop('dst')
            r = mkdir(dst, **d).diff()
            if r['diff']:
                res['diff'] += r['diff']
                res['changed'].append(dst)
        return res


class rm(Task):
    """rm a file or directory"""

    def __init__(self, dst=None, **kwargs):
        kwargs.setdefault('name', dst)
        kwargs.setdefault('dst', dst)
        super(rm, self).__init__(**kwargs)

    def do(self):
        changed = False
        for dst in glob.glob(self.args['dst']):
            if os.path.exists(dst):
                try:
                    if os.path.isdir(dst):
                        import shutil
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                    changed = True
                except OSError:
                    exc = self.format_exception()
                    return dict(rc=1, exc=exc)
        return dict(rc=0, changed=changed)

    def diff(self):
        diff = ''
        filenames = []
        for dst in glob.glob(self.args['dst']):
            if os.path.exists(dst):
                filenames.append(dst + '\n')
        if filenames:
            res = self.lists_diff(filenames, [], fromfile=dst)
            diff = u''.join(res) + u'\n'
        return dict(rc=0, diff=diff)


class mv(Task):
    """rename/move a file or a directory"""

    def __init__(self, src=None, dst=None, **kwargs):
        kwargs.setdefault('name', src)
        super(mv, self).__init__(src=src, dst=dst, **kwargs)

    def do(self):
        src = self.args['src']
        dst = self.args['dst']
        if not os.path.exists(src) and os.path.exists(dst):
            # Consider the task already done
            return dict(rc=0, changed=False)
        try:
            os.rename(src, dst)
        except OSError:
            exc = self.format_exception()
            return dict(rc=1, exc=exc)
        return dict(rc=0, changed=True)

    def diff(self):
        src = self.args['src']
        dst = self.args['dst']
        diff = ''
        if os.path.exists(src):
            diff += "%s -> %s\n" % (src, dst)
        return dict(rc=0, diff=diff)


class chmod(Task):
    """apply chmod to dst"""

    diff = False

    def __init__(self, dst=None, mod='644', recursive=False, **kwargs):
        kwargs.setdefault('name', dst)
        super(chmod, self).__init__(dst=dst, mod=mod,
                                    recursive=recursive, **kwargs)

    def do(self):
        dst = self.args['dst']
        mod = self.args['mod']
        recursive = self.args['recursive']
        utils.chmod(dst, mod, recursive=recursive)
        return dict(rc=0, dst=dst, mod=mod)


class chown(Task):
    """apply chown to dst"""

    diff = False

    def __init__(self, dst=None, own='root:root', recursive=False, **kwargs):
        kwargs.setdefault('name', dst)
        super(chown, self).__init__(dst=dst, own=own,
                                    recursive=recursive, **kwargs)

    def do(self):
        dst = self.args['dst']
        own = self.args['own']
        recursive = self.args['recursive']
        utils.chown(dst, own, recursive=recursive)
        return dict(rc=0, dst=dst, own=own)


class put(Task):
    """put files on the remote host"""

    def __init__(self, files=None, **kwargs):
        kwargs.setdefault('name', [f['dst'] for f in files or []])
        super(put, self).__init__(files=files, **kwargs)

    def pre_process(self):
        for fd in self.args['files']:
            if 'linkto' in fd:
                fd['data'] = None
            elif 'src' in fd:
                src = fd['src']
                if src.startswith('~/'):
                    fd['src'] = os.path.expanduser(src)
                if src.endswith(('.j2', '.j2.gpg')):
                    self.render_template(fd)
                else:
                    self.render_file(fd)
            elif 'tpl' in fd:
                src = fd['src'] = fd['tpl']
                if src.startswith('~/'):
                    fd['src'] = os.path.expanduser(src)
                self.render_template(fd)
            if 'data' not in fd:
                raise RuntimeError('cant get content for fd {0}'.format(fd))

    def do(self):
        files = self.args['files'] or []
        files_changed = []
        for fd in files:
            dst = fd['dst']
            if dst.startswith('~/'):
                dst = fd['dst'] = os.path.expanduser(dst)
            if 'linkto' in fd:
                link = fd['linkto']
                if os.path.exists(dst):
                    if os.path.islink(dst):
                        if os.path.realpath(dst) != os.path.realpath(link):
                            os.unlink(dst)
                    else:
                        os.remove(dst)
                if not os.path.exists(link):
                    self.send_log((
                        'Invalid link destination for '
                        '{0[dst]} -> no such file {0[linkto]}'
                        ).format(fd), level=logging.ERROR)
                if not os.path.islink(dst):
                    os.symlink(link, dst)
                    files_changed.append(dst)
            else:
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
                mod = (
                    st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
                )
            if mod is not None:
                utils.chmod(dst, mod)
        return dict(rc=0, changed=files_changed)

    def diff(self):
        diff = ''
        files = self.args['files'] or []
        files_changed = []
        for fd in files:
            dst = fd['dst']
            if 'linkto' in fd:
                if os.path.exists(fd['linkto']):
                    new_text = '{0[dst]} -> {0[linkto]}\n'.format(fd)
                else:
                    new_text = (
                        '{0[dst]} -> no such file {0[linkto]}\n'
                    ).format(fd)
                    self.send_log((
                        'Invalid link destination for {0}'
                        ).format(new_text.strip()),
                        level=logging.ERROR)
                if not os.path.isfile(dst):
                    old_text = ''
                else:
                    old_text = new_text
            else:
                new_text = fd['data']
                if not os.path.isfile(dst):
                    old_text = ''
                else:
                    with codecs.open(dst, 'rb', 'utf8') as fd_:
                        old_text = fd_.read()
            if old_text != new_text:
                files_changed.append(dst)
            diff += self.texts_diff(old_text, new_text, fromfile=dst)
        return dict(rc=0, diff=diff, changed=files_changed)


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
