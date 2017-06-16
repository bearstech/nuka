# -*- coding: utf-8 -*-
from collections import defaultdict
from functools import partial
import ipaddress
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

_env_keys = {
    Provider.GCE: (
        ('GCE_EMAIL', 'user_id'),
        ('GCE_PEM_FILE_PATH', 'key'),
        ('GCE_PROJECT', 'project'),
    ),
    Provider.OPENSTACK: (
        ('OS_VERSION', '2.0'),
        ('OS_AUTH_URL', 'auth_url'),
        ('OS_USERNAME', 'username'),
        ('OS_PASSWORD', 'password'),
        ('OS_PROJECT_NAME', 'project_name'),
        ('OS_PROJECT_ID', 'project_id'),
        ('OS_TENANT_NAME', 'project_name'),
        ('OS_TENANT_ID', 'project_id'),
        ('OS_REGION_NAME', 'region_name'),
    )
}


def driver_from_config(provider, **args):
    # cache one driver per thread. probably only usefull for main thread
    ident = threading.get_ident()
    driver = _drivers[provider].get(ident)
    if driver is None:
        if provider in nova_providers:
            klass = NovaClient
        else:
            klass = get_driver(provider)

        if not args:
            args = nuka.config[provider.lower()].get('driver', {}) or {}
            if isinstance(args, str):
                # load arguments from file
                with open(os.path.expanduser(args)) as fd:
                    args = utils.json.load(fd)

            for k, new_k in _env_keys.get(provider, ()):
                if k in os.environ:
                    v = os.environ[k]
                    args[new_k] = v
            if not args:
                raise RuntimeError((
                    'Not able to get the driver configuration for {} provider.'
                ).format(provider))

        driver = klass(**args)
        _drivers[ident] = driver
    return driver


class Host(base.Host):
    """Host in the cloud"""

    use_sudo = True

    def __init__(self, hostname, node=None,
                 create=True, driver_args=None, create_node_args=None, **vars):
        config = nuka.config.get(self.provider.lower(), {})
        user = config.get('user') or 'root'
        vars.setdefault('user', user)
        vars['driver_args'] = driver_args or {}
        vars['create_node_args'] = create_node_args or {}
        super().__init__(hostname, **vars)
        self.create = create
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
        """return host's public ip"""
        return self.node.public_ips[0]

    @property
    def private_ip(self):
        """return host's private ip"""
        return self.node.private_ips[0]

    def get_node(self, task=None, **kwargs):
        if self._node is False:
            raise RuntimeError('Node {0} was destroyed'.format(self))
        elif self._node is None:

            with self.timeit(type='api_call', task=task,
                             name='Driver.from_config()'):
                driver = driver_from_config(provider=self.provider,
                                            **self.driver_args)

            with self.timeit(type='api_call', task=task,
                             name='driver.ex_get_node()'):
                try:
                    if self.provider in nova_providers:
                        self._node = driver.servers.find(name=self.hostname)
                    else:
                        self._node = driver.ex_get_node(self.hostname)
                except (ResourceNotFoundError, NotFound):
                    pass
            if self._node is None and self.create:
                self.create_node(driver=driver, task=task)
        return self._node
    node = property(get_node)

    def create_node(self, driver=None, task=None, **kwargs):
        self.log.warning(
            'Node {0} does not exist. Creating...'.format(self))
        if driver is None:
            driver = driver_from_config(provider=self.provider,
                                        **self.driver_args)
        args = self.get_create_node_args(driver=driver, task=task)
        args['name'] = self.name
        with self.timeit(type='api_call', task=task,
                         name='driver.ex_create_node()'):
            if self.provider in nova_providers:
                node = driver.servers.create(**args)
                # it take at least 20s to boot a vm
                time.sleep(20)
                wait = 15
                while node.status not in ('ACTIVE',):
                    try:
                        node = driver.servers.find(name=self.hostname)
                    except NotFound:
                        pass
                    if node.status in ('ACTIVE',):
                        # need to wait ~10s to get the server up & running
                        time.sleep(10)
                        break
                    else:
                        wait = (wait - 5)
                        if wait < 1:
                            wait = 2
                        time.sleep(wait)
                self._node = node
            else:
                self._node = driver.create_node(**args)
            self.log.warning('Node {0} created'.format(self))

    def get_create_node_args(self, driver=None, task=None):
        provider_args = nuka.config.get(self.provider.lower(), {})
        node_args = provider_args.get('create_node_args', {}).copy()
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
            with self.timeit(type='api_call', task=task,
                             name='Driver.ex_list_networks()'):
                net = driver.ex_list_networks()[0]
            node_args['ex_network'] = net

        return node_args


class OpenstackHost(Host):
    """Host on OpenStack"""

    use_sudo = True
    provider = Provider.OPENSTACK

    def _set_ips(self):
        for iface in self.node.interface_list():
            for addr in iface.fixed_ips:
                ip = addr['ip_address']
                try:
                    a = ipaddress.IPv4Address(ip)
                except ValueError:
                    continue
                else:
                    if not a.is_private:
                        if 'public_ip' not in self.vars:
                            self.vars['public_ip'] = ip
                    else:
                        if 'private_ip' not in self.vars:
                            self.vars['private_ip'] = ip
        if 'private_ip' not in self.vars:
            # we may not have a private net
            self.vars['private_ip'] = self.vars['public_ip']

    @property
    def public_ip(self):
        """return host's public ip"""
        if 'public_ip' not in self.vars:
            self._set_ips()
        return self.vars['public_ip']

    @property
    def private_ip(self):
        if 'private_ip' not in self.vars:
            self._set_ips()
        return self.vars['private_ip']

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
            driver = driver_from_config(self.provider, **self.driver_args)
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

    def __init__(self, provider=None, driver_args=None,
                 create=True, use_sudo=False):
        if provider is None:
            raise RuntimeError('A cloud instance require a valid provider')
        self.provider = provider
        self.driver_args = driver_args or {}
        self.create = create
        if provider in self.host_classes:
            self.host_class = self.host_classes[self.provider]
        else:
            name = '{0}Host'.format(self.provider.title())
            args = {'provider': self.provider, 'use_sudo': use_sudo}
            self.host_class = type(name, (Host,), args)
        self._nodes = {}

    @property
    def driver(self):
        return driver_from_config(self.provider, **self.driver_args)

    @property
    def cached_list_nodes(self):
        cls = self.__class__
        if not self._nodes:
            cls._list_lock.acquire()
            if self.provider in nova_providers:
                self._nodes = {n.name: n for n in self.driver.servers.list()}
            else:
                self._nodes = {n.name: n for n in self.driver.list_nodes()}
            cls._list_lock.release()
        return self._nodes

    def __getitem__(self, item):
        if item not in self:
            item = item.replace('_', '-')
        return super().__getitem__(item)

    def get_or_create_node(self, hostname, **kwargs):
        """Return a Host. Create it if needed"""
        kwargs.setdefault('create', self.create)
        kwargs['driver_args'] = self.driver_args
        if hostname not in self:
            kwargs.setdefault('node', self._nodes.get(hostname))
            self[hostname] = self.host_class(hostname=hostname, **kwargs)
        return self[hostname]

    def get_node(self, hostname, **kwargs):
        """Return a Host. Create it if needed"""
        kwargs['create'] = False
        host_node = self._nodes.get(hostname)
        return self.get_or_create_node(hostname, node=host_node, **kwargs)

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
        for node in self.cached_list_nodes.values():
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
    for node in cloud.cached_list_nodes.values():
        cloud.get_or_create_node(node.name, node=node)
    return cloud
