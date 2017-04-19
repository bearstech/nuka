# -*- coding: utf-8 -*-
from collections import defaultdict
from functools import partial
import threading
import asyncio
import codecs
import time
import os

from libcloud.common.google import ResourceNotFoundError
from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider

from novaclient.client import Client as NovaClient
from novaclient.exceptions import NotFound

from nuka.task import get_task_from_stack
from nuka.hosts import base
from nuka import utils
import nuka


nova_providers = (Provider.OPENSTACK,)


_drivers = defaultdict(dict)


def driver_from_config(provider):
    # cache one driver per thread. probably only usefull for main thread
    ident = threading.get_ident()
    driver = _drivers[provider].get(ident)
    if driver is None:
        if provider in nova_providers:
            klass = NovaClient
        else:
            klass = get_driver(provider)
        args = nuka.config[provider.lower()]['driver']
        if isinstance(args, str):
            # load arguments from file
            with open(os.path.expanduser(args)) as fd:
                args = utils.json.load(fd)
        driver = klass(**args)
        _drivers[ident] = driver
    return driver


class Host(base.Host):
    """Host in the cloud"""

    use_sudo = True

    def __init__(self, hostname, node=None, create_node_args=None, **vars):
        config = nuka.config.get(self.provider.lower(), {})
        user = config.get('user') or 'root'
        vars.setdefault('user', user)
        vars['create_node_args'] = create_node_args or {}
        super().__init__(hostname, **vars)
        self._node = node

    async def boot(self):
        # we need to get the task from here.
        # we cant retrieve it while in an executor
        task = get_task_from_stack()
        get_node = partial(self.get_node, task=task)
        try:
            self._node = await self.loop.run_in_executor(None, get_node)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(type(e))
            self.log.exception('boot')
            self.cancel()
            raise
        else:
            self.hostname = self.public_ip

    @property
    def public_ip(self):
        return self.node.public_ips[0]

    @property
    def private_ip(self):
        return self.node.private_ips[0]

    def get_node(self, create=True, task=None, **kwargs):
        if self._node is False:
            raise RuntimeError('Node {0} was destroyed'.format(self))
        elif self._node is None:

            start = time.time()
            driver = driver_from_config(provider=self.provider)
            self.add_time(start=start, type='api_call', task=task,
                          name='Driver.from_config()')

            start = time.time()
            try:
                if self.provider in nova_providers:
                    self._node = driver.servers.find(name=self.hostname)
                else:
                    self._node = driver.ex_get_node(self.hostname)
            except (ResourceNotFoundError, NotFound):
                self.add_time(start=start, type='api_call', task=task,
                              name='driver.ex_get_node()')
                if create:
                    self.log.warn(
                        'Node {0} does not exist. Creating...'.format(self))
                    args = self.get_create_node_args(driver=driver, task=task)
                    args['name'] = self.name
                    start = time.time()
                    if self.provider in nova_providers:
                        self._node = driver.servers.create(**args)
                    else:
                        self._node = driver.create_node(**args)
                    self.log.warn('Node {0} created'.format(self))
                    self.add_time(start=start, type='api_call', task=task,
                                  name='driver.ex_create_node()')
            else:
                self.add_time(start=start, type='api_call', task=task,
                              name='driver.ex_get_node()')
        return self._node
    node = property(get_node)

    def get_create_node_args(self, driver=None, task=None):
        node_args = nuka.config[self.provider.lower()]['create_node_args']
        node_args = node_args.copy()
        node_args.update(self.vars.get('create_node_args'))
        self.log.debug4(nuka.utils.json.dumps(node_args, indent=2))
        return node_args

    async def destroy(self, **kwargs):
        raise NotImplementedError(
            'Please use Cloud.destroy() which is mush faster')


class GCEHost(Host):
    """Host on GCE"""

    use_sudo = True
    provider = Provider.GCE

    def get_create_node_args(self, driver=None, task=None):
        node_args = super().get_create_node_args(driver=driver, task=task)

        # update ex_metadata ssh keys
        keys_list = nuka.config.get('ssh', {}).get('keys') or []
        keysfile = nuka.config.get('ssh', {}).get('keysfile')
        if keysfile:
            with codecs.open(os.path.expanduser(keysfile), 'r', 'utf8') as fd:
                for line in fd:
                    keys_list.append(line.strip())
        if keys_list:
            node_args.setdefault('ex_metadata', {})
            items = node_args['ex_metadata'].setdefault('items', [])
            if not [v for v in items if v["key"] == "sshKeys"]:
                keys = []
                for line in keys_list:
                    if ':' in line:
                        keys.append(line)
                    else:
                        keys.append(self.vars['user'] + ':' + line)
                keys = '\n'.join(keys)
                items.append({"value": keys, "key": "sshKeys"})

        self.log.debug4(nuka.utils.json.dumps(node_args, indent=2))

        if 'ex_network' not in node_args:
            start = time.time()
            net = driver.ex_list_networks()[0]
            self.add_time(start=start, type='api_call', task=task,
                          name='Driver.ex_list_networks()')
            node_args['ex_network'] = net

        return node_args


class OpenstackHost(Host):
    """Host on OpenStack"""

    use_sudo = True
    provider = Provider.OPENSTACK

    @property
    def public_ip(self):
        for iface in self.node.interface_list():
            for addr in iface.fixed_ips:
                ip = addr['ip_address']
                if ':' not in ip:
                    return ip

    @property
    def private_ip(self):
        raise NotImplementedError()

    def get_create_node_args(self, driver=None, task=None):
        node_args = super().get_create_node_args(driver=driver, task=task)

        # update ex_metadata ssh keys
        keys_list = nuka.config.get('ssh', {}).get('keys') or []
        keysfile = nuka.config.get('ssh', {}).get('keysfile')
        if keysfile:
            with codecs.open(os.path.expanduser(keysfile), 'r', 'utf8') as fd:
                for line in fd:
                    keys_list.append(line.strip())
        if keys_list:
            driver = driver_from_config(self.provider)
            keypairs = [k for k in driver.keypairs.list() if k.name == 'ops']
            if not keypairs:
                driver.keypairs.create(
                    name='ops',
                    public_key='\n'.join(keys_list),
                )
            node_args['key_name'] = 'ops'
        self.log.debug4(nuka.utils.json.dumps(node_args, indent=2))
        if 'flavor' in node_args:
            node_args['flavor'] = driver.flavors.find(name=node_args['flavor'])
        if 'image' in node_args:
            node_args['image'] = driver.glance.find_image(node_args['image'])
        return node_args


class Cloud(base.HostGroup):
    """A HostGroup of cloud hosts"""

    _list_lock = threading.Lock()
    _nodes = {}

    host_classes = {
        Provider.GCE: GCEHost,
        Provider.OPENSTACK: OpenstackHost,
    }

    def __init__(self, provider=Provider.GCE, use_sudo=False):
        self.provider = provider
        if provider in self.host_classes:
            self.host_class = self.host_classes[self.provider]
        else:
            name = '{0}Host'.format(self.provider.title())
            args = {'provider': self.provider, 'use_sudo': use_sudo}
            self.host_class = type(name, (Host,), args)

    @property
    def driver(self):
        return driver_from_config(self.provider)

    def cached_list_nodes(self):
        cls = self.__class__
        if not cls._nodes.get(self.provider):
            cls._list_lock.acquire()
            if not cls._nodes.get(self.provider):
                if self.provider in nova_providers:
                    cls._nodes[self.provider] = self.driver.servers.list()
                else:
                    cls._nodes[self.provider] = self.driver.list_nodes()
            cls._list_lock.release()
        return cls._nodes[self.provider]

    def __getitem__(self, item):
        if item not in self:
            item = item.replace('_', '-')
        return super().__getitem__(item)

    def get_or_create_node(self, hostname, **kwargs):
        """Return a Host. Create it if needed"""
        node = kwargs.pop('node', None)
        if hostname not in self:
            self[hostname] = self.host_class(hostname=hostname, **kwargs)
        if node is not None:
            self.hostname._node = node
        return self[hostname]

    def from_compose(self, project_name=None, filename='docker-compose.yml'):
        """Return a host group with hosts names extracted from compose file"""
        from compose.project import Project
        from compose import config

        project_dir = os.getcwd()
        project_name = project_name or os.path.basename(project_dir)
        conf = config.load(
            config.find(project_dir, [filename], os.environ)
        )
        project = Project.from_config('', conf, client=None)
        for service in project.get_services():
            name = '{0}-{1.name}-1'.format(project_name, service)
            self.get_or_create_node(hostname=name)
        return self

    async def destroy(self):
        """Destroy all hosts in the group"""
        nodes = []
        for node in self.cached_list_nodes():
            if node.name in self:
                nodes.append(node)
                self[node.name].log.info('destroy()')
        if nodes:
            if self.provider in nova_providers:
                for node in nodes:
                    try:
                        node.force_delete()
                    except:
                        if node.name in self:
                            host = self[node.name]
                            host.log.exception('destroy()')
                        else:
                            raise

            else:
                self.driver.ex_destroy_multiple_nodes(nodes)
            del self[node.name]


def get_cloud(provider=Provider.GCE):
    """return a :class:`nuka.hosts.Cloud` filled with all instanciated hosts"""
    cloud = Cloud(provider=provider)
    for node in cloud.cached_list_nodes():
        cloud.get_or_create_node(node.name, node=node)
    return cloud
