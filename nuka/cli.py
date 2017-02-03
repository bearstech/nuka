import sys
import argparse

from nuka.configuration import config


class Cli(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.args = None
        self.add_argument(
            '--help', '-h', action='store_true',
            required=False, default=False,
            help='show this help and exit')
        self.add_argument(
            '--config', '-c', type=argparse.FileType('r'),
            required=False, default=None,
            help='yaml config file')
        self.add_argument('--diff', '-d', action='store_true', default=False,
                          help='run in diff mode')
        self.add_argument('--verbose', '-v', action='count', default=0,
                          help='increase verbosity')
        self.add_argument('--tempdir', default=None)
        self.add_argument('--debug', action='store_true', default=False,
                          help='enable asyncio debug')
        self.add_argument('--uvloop', action='store_true', default=False,
                          help='use uvloop as eventloop')

    def parse_args(self, argv=None):
        self.args = super().parse_args(argv)
        if self.args.help:
            self.print_help()
            # Ignore warnings like:
            # sys:1: RuntimeWarning: coroutine 'do_something' was never awaited
            import warnings
            warnings.simplefilter("ignore")
            sys.exit(0)
        if self.args.config:
            config.update_from_file(self.args.config)
        config.finalize(self.args)


cli = Cli(add_help=False)

if config['testing']:
    cli.parse_args(['-vvvvvv', '--tempdir=/tmp/nuka_provisionning'])
