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

import logging
import sys
import os

import nuka
from nuka.utils import LOG
from nuka.utils import CHANGED


class HostLogger(logging.Logger):
    """Logger for a host that can log to a file and stdout at different
    levels"""

    def __init__(self, host):
        self.host = host
        stream_level = nuka.config['log']['levels']['stream_level']
        file_level = nuka.config['log']['levels']['file_level']
        super().__init__(host, max(stream_level, file_level))
        if stream_level is not None:
            if nuka.config['log']['quiet']:
                filename = nuka.config['log']['stdout']
                self.addHandler(HostFileHandler(host, level=stream_level,
                                                filename=filename))
            else:
                self.addHandler(HostStreamHandler(host, level=stream_level))
        self.addHandler(HostFileHandler(host, level=file_level))

    def changed(self, *args, **kwargs):
        self.log(CHANGED, *args, **kwargs)

    def __call__(self, msg, *args, **kwargs):
        self.log(LOG, msg, *args, **kwargs)

    def _extra_logs(self, level, i, *args, **kwargs):
        if nuka.cli.args.verbose > i:
            self.log(level, *args, **kwargs)

    def debug2(self, *args, **kwargs):
        self._extra_logs(logging.DEBUG, 2, *args, **kwargs)

    def debug3(self, *args, **kwargs):
        self._extra_logs(logging.DEBUG, 3, *args, **kwargs)

    def debug4(self, *args, **kwargs):
        self._extra_logs(logging.DEBUG, 4, *args, **kwargs)

    def debug5(self, *args, **kwargs):
        self._extra_logs(logging.DEBUG, 5, *args, **kwargs)

    def exception5(self, *args, **kwargs):
        if nuka.cli.args.verbose > 5:
            self.exception(*args, **kwargs)


class HostFileHandler(logging.FileHandler):

    __rollover = False

    def __init__(self, host, level, filename=None):
        self.host = host
        logdir = nuka.config['log']['dirname']
        if filename:
            self.filename = filename
            if not self.__rollover:
                # if filename is specified, rollover only once during run time
                self.__class__.__rollover = True
                self.rollover()
        else:
            self.filename = os.path.join(logdir, '{0}.log'.format(host))
            self.rollover()
        if not os.path.isdir(os.path.dirname(self.filename)):
            os.makedirs(os.path.dirname(self.filename))
        super().__init__(self.filename, 'w')
        fmt = nuka.config['log']['formats']['default']
        self.setFormatter(logging.Formatter(fmt))
        self.setLevel(level)

    def rollover(self):
        for i in range(9 - 1, 0, -1):
            sfn = "%s.%d" % (self.filename, i)
            dfn = "%s.%d" % (self.filename, i + 1)
            if os.path.exists(sfn):
                if os.path.exists(dfn):
                    os.remove(dfn)
                os.rename(sfn, dfn)
        dfn = self.filename + ".1"
        if os.path.exists(dfn):
            os.remove(dfn)
        if os.path.exists(self.filename):
            os.rename(self.filename, dfn)


class HostStreamHandler(logging.StreamHandler):

    reset = "\033[0m"

    def __init__(self, host, level):
        self.host = host
        super().__init__(sys.stdout)
        fmt = nuka.config['log']['formats']['host'].format(host)
        self.setFormatter(logging.Formatter(fmt))
        self.setLevel(level)

    def format(self, record):
        res = super().format(record)
        col = nuka.config['log']['colors'].get(record.levelno, '')
        res = res.split('\n', 1)
        if len(res) > 1:
            res = ''.join([col, res[0] + self.reset, '\n'] + res[1:])
        else:
            res = col + res[0] + self.reset
        return res
