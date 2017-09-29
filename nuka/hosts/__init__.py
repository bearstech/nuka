# -*- coding: utf-8 -*-
"""
Host
====

.. autoclass:: HostGroup
   :members:

.. autoclass:: Host
   :members:

Docker
======

.. autoclass:: DockerCompose
   :members:

.. autoclass:: DockerContainer
   :members:

Vagrant
=======

.. autoclass:: Vagrant
   :members:


Libcloud
========

.. autoclass:: Cloud
   :members:
"""
from .base import all_hosts  # NOQA
from .base import Host  # NOQA
from .base import LocalHost  # NOQA
from .base import Chroot  # NOQA
from .base import HostGroup  # NOQA
from .vagrant import Vagrant  # NOQA

try:
    import compose  # NOQA
except ImportError:  # pragma: no cover
    # docker is not available
    pass
else:
    from .docker_host import DockerContainer  # NOQA
    from .docker_host import DockerCompose  # NOQA

try:
    import libcloud  # NOQA
    import novaclient # NOQA
except ImportError:  # pragma: no cover
    # licloud is not available
    pass
else:
    from .cloud import Cloud  # NOQA
    from .cloud import get_cloud  # NOQA
    from .cloud import Provider  # NOQA
