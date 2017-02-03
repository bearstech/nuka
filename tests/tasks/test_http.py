# -*- coding: utf-8 -*-
import os
import pytest
import nuka
from nuka.tasks import http


@pytest.mark.asyncio
async def test_fetch(host):
    res = await http.fetch('http://bearstech.com')
    assert res.dst == os.path.join(nuka.config['remote_tmp'], 'bearstech.com')
    res = await http.fetch('http://bearstech.com', dst='/tmp/bt.com')
    assert res.dst == '/tmp/bt.com'
