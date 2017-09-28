import sys
import argparse

from nuka.configuration import config


class Cli(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        kwargs['add_help'] = True
        super().__init__(*args, **kwargs)
        self.finalized = False
        self.args = None
        self.help = None
        self.add_argument(
            '-c', '--config', type=argparse.FileType('r'),
            required=False, default=None,
            help='yaml config file')
        self.add_argument('--diff', action='store_true', default=False,
                          help='run in diff mode')

        verbosity = self.add_argument_group('verbosity')
        verbosity.add_argument('-v', '--verbose', action='count', default=0,
                               help='increase verbosity')
        verbosity.add_argument('-q', '--quiet',
                               action='store_true', default=False,
                               help='log to stoud.log instead of stdout')
        verbosity.add_argument('--debug', action='store_true', default=False,
                               help='enable asyncio debug')

        dirs = self.add_argument_group('directories')
        dirs.add_argument(
            '--tempdir', default=None,
            help='tempdir name to store file localy and remotly')
        dirs.add_argument(
            '--nuka-dir', default=None,
            help='directory to store logs & reports. Default: .nuka')

        proc = self.add_argument_group('processes')
        proc.add_argument('-d', '--connections-delay', type=float,
                          metavar='DELAY', default=.2,
                          help='delay ssh connections. Default: 0.2')
        misc = self.add_argument_group('misc')
        misc.add_argument('--ssh', action='store_true', default=False,
                          help='use ssh binary instead of asyncssh')
        misc.add_argument('--uvloop', action='store_true', default=False,
                          help='use uvloop as eventloop')

    @property
    def arguments(self):
        return list(self._option_string_actions)

    def parse_known_args(self, *args, **kwargs):
        self.args, argv = super().parse_known_args(*args, **kwargs)
        return self.args, argv

    def print_help(self):
        self.help = True
        # Ignore warnings like:
        # sys:1: RuntimeWarning: coroutine 'do_something' was never awaited
        import warnings
        warnings.simplefilter("ignore")
        super().print_help()

    def parse_args(self, *args, **kwargs):
        self.args = super().parse_args(*args, **kwargs)
        if self.args.config:
            config.update_from_file(self.args.config)
        config.finalize(self.args)
        self.finalized = True


cli = Cli(add_help=False)

if config['testing']:
    cli.parse_args(['-vvvvvv', '--tempdir=/tmp/nuka_provisionning'])
