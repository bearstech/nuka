# Copyright 2017 by Bearstech <py@bearstech.com>
#
# This file is part of nuka.
#
# nuka is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# nuka is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with nuka. If not, see <http://www.gnu.org/licenses/>.

import os
import yaml
import subprocess

import jinja2
from jinja2.utils import open_if_exists
from jinja2.loaders import split_template_path
from jinja2.exceptions import TemplateNotFound


class FileSystemLoader(jinja2.FileSystemLoader):

    def get_source(self, environment, template):
        pieces = split_template_path(template)
        for searchpath in self.searchpath:
            filename = os.path.join(searchpath, *pieces)
            f = open_if_exists(filename)
            if f is None:
                continue
            if filename.endswith('.gpg'):
                f.close()
                _, contents = decrypt(filename, self.encoding)
            else:
                try:
                    contents = f.read().decode(self.encoding)
                finally:
                    f.close()

            mtime = os.path.getmtime(filename)

            def uptodate():
                try:
                    return os.path.getmtime(filename) == mtime
                except OSError:
                    return False
            return contents, filename, uptodate
        raise TemplateNotFound(template)


def decrypt(filename, encoding='utf8'):
    cmd = ['gpg', '--quiet', '--batch', '-d', filename]
    try:
        value = subprocess.check_output(cmd)
    except subprocess.CalledProcessError:
        raise
        raise RuntimeError((
            'Error while trying to decrypt {0}. '
            'Maybe your GPG agent has expired'.format(filename)))
    if filename.endswith('.gpg'):
        filename = filename[:-4]
    if filename.endswith(('.yaml', '.yml')):
        return yaml.load(value)
    if isinstance(value, bytes):
        value = value.decode(encoding)
    return filename, value
