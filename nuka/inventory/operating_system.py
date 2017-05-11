# -*- coding: utf-8 -*-
import os
import codecs

DEBIAN_RELEASES = (
    (u'9.', u'stretch'),
    (u'8.', u'jessie'),
    (u'7.', u'squeeze')
)


def update_inventory(inventory):
    infos = {'name': None, 'version': None, 'release': None}
    if os.path.isfile('/etc/debian_version'):
        infos['name'] = 'debian'
        with codecs.open('/etc/debian_version', 'r', 'utf8') as fd:
            version = fd.read().strip()
            infos['version'] = version
        for ver, name in DEBIAN_RELEASES:
            if version.startswith(ver):
                infos['release'] = name
                break
    inventory['os'] = infos
