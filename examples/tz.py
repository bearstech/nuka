# -*- coding: utf-8 -*-
import nuka
from nuka.hosts import DockerContainer

from tasks.timezone import timezone

host = DockerContainer(hostname='debian_jessie')


async def change_timezone(host):
    await timezone(tz='Europe/Paris')


nuka.run(change_timezone(host))
