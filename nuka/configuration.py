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
import tempfile
import logging
import os

import jinja2
import yaml

from nuka.utils import CHANGED
from nuka.gpg import FileSystemLoader


asyncio_logger = logging.getLogger('asyncio')


class Config(dict):

    def update_from_file(self, yaml_config):  # pragma: no cover
        for doc in yaml.load_all(yaml_config):
            for k, v in doc.items():
                if isinstance(v, dict):
                    self.setdefault(k, v)
                    self[k].update(v)
                else:
                    self[k] = v

    def finalize(self, args):
        if args.nuka_dir:
            self['nuka_dir'] = args.nuka_dir
        nuka_dir = self['nuka_dir']
        tempdir = args.tempdir or tempfile.mkdtemp(prefix='nuka')
        self['tmp'] = tempdir
        for dirname in (nuka_dir, tempdir):
            if not os.path.isdir(dirname):  # pragma: no cover
                os.makedirs(dirname)

        for name in ('log', 'reports', 'ssh'):
            for key, value in self[name].items():
                if isinstance(value, str):
                    value = value.format(nuka_dir=nuka_dir)
                    self[name][key] = value
                    if key == 'dirname':
                        if not os.path.isdir(value):  # pragma: no cover
                            os.makedirs(value)

        # set correct path in self
        opts = self['ssh']['options']
        opts.extend(self['ssh'].get('extra_options', []))
        self['ssh']['options'] = []
        for o in opts:
            self['ssh']['options'].append(o.format(**config['ssh']))

        self['remote_dir'] = os.path.join(tempdir, 'nuka')
        self['remote_tmp'] = os.path.join(tempdir, 'tmp')
        self['script'] = os.path.join(config['remote_dir'], 'script.py')

        if args.verbose == 1:  # pragma: no cover
            self['log']['levels']['stream_level'] = logging.INFO
            self['log']['levels']['file_level'] = logging.INFO
            self['log']['levels']['remote_level'] = logging.WARN
        elif args.verbose == 2:  # pragma: no cover
            self['log']['levels']['stream_level'] = logging.INFO
            self['log']['levels']['file_level'] = logging.DEBUG
            self['log']['levels']['remote_level'] = logging.INFO
        elif args.verbose > 2:
            self['log']['levels']['stream_level'] = logging.DEBUG
            self['log']['levels']['file_level'] = logging.DEBUG
            self['log']['levels']['remote_level'] = logging.DEBUG

        if args.verbose < 3:
            asyncio_logger.setLevel(logging.CRITICAL)

        if args.quiet or 'quiet' not in self['log']:
            self['log']['quiet'] = args.quiet

        if args.connections_delay or 'delay' not in self['connections']:
            self['connections']['delay'] = args.connections_delay

    def get_template_engine(self):
        engine = self.get('template_engine')
        if engine is None:
            templates = self['templates']
            dirname = os.path.join(os.getcwd(), 'templates')
            if os.path.isdir(dirname):  # pragma: no cover
                if dirname not in templates:
                    templates.insert(0, dirname)
            elif os.getcwd() not in templates:
                templates.insert(0, os.getcwd())
            loader = jinja2.ChoiceLoader([
                FileSystemLoader(p) for p in templates
            ] + [jinja2.PackageLoader('nuka')])
            self['template_engine'] = jinja2.Environment(
                loader=loader,
                undefined=jinja2.StrictUndefined,
                keep_trailing_newline=True,
                autoescape=False,
            )
        return self['template_engine']


config = Config()
config['id'] = id(config)
config['testing'] = 'TESTING' in os.environ
config['templates'] = []

config['nuka_dir'] = '.nuka'

config['inventory_modules'] = []

config['sudo'] = 'sudo'
config['su'] = 'su -l'

config['docker'] = {
    'use_api': False,
}

config['ssh'] = {
    'dirname': '{nuka_dir}/ssh',
    'options': [
       '-oControlMaster=auto',
       '-oControlPersist=300s',
       '-oControlPath={dirname}/%r@%h:%p',
    ],
}
config['connections'] = {'delay': .2}
config['log'] = {
    'dirname': '{nuka_dir}/logs',
    'stdout': '{nuka_dir}/logs/stdout.log',
    'formats': {
        'default': '%(levelname)-5.5s: %(message)s',
        'host': '%(levelname)-5.5s:{0.name:15.15}: %(message)s',
    },
    'levels': {
        'stream_level': CHANGED,
        'file_level': logging.INFO,
        'remote_level': logging.INFO,
    },
    'colors': {
        logging.ERROR: "\033[01;31m",
        logging.CRITICAL: "\033[01;31m",
        logging.WARN: "\033[01;35m",
        CHANGED: "\033[01;35m",
    }
}
config['reports'] = {
    'dirname': '{nuka_dir}/reports',
}
