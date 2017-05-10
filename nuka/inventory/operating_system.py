# -*- coding: utf-8 -*-
import os
import codecs


def update_inventory(inventory):
    infos = {'name': None, 'version': None, 'release': None}
    if os.path.isfile('/etc/debian_version'):
        infos['name'] = 'debian'
        with codecs.open('/etc/debian_version') as fd:
            version = fd.read().strip()
            infos['version'] = version
        releases = ((u'9.', u'stretch'), (u'8.', u'jessie'))
        for ver, name in releases:
            if version.startswith(ver):
                infos['release'] = name
                break
    inventory['os'] = infos
