# -*- coding: utf-8 -*-
from nuka.tasks import file
import pytest
import os

pytestmark = [
    pytest.mark.skipif(
        'gawel' not in os.getenv('GPG_AGENT_INFO', ''),
        reason='gawel not found in GPG_AGENT_INFO')
]


@pytest.mark.asyncio
async def test_gpg_file(host):
    res = await file.put([dict(src='tests/templates/gpg.txt.gpg',
                               dst='/tmp/gpg.txt')])
    assert bool(res)
    res = await file.cat('/tmp/gpg.txt')
    assert res.content == 'yo {{name}}\n'


@pytest.mark.asyncio
async def test_gpg_template(host):
    res = await file.put([dict(src='gpg.j2.gpg', dst='/tmp/gpg.j2')],
                         ctx=dict(name='dude'))
    assert bool(res)
    res = await file.cat('/tmp/gpg.j2')
    assert res.content == 'yo dude\n'
