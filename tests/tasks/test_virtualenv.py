# -*- coding: utf-8 -*-
import os
import pytest
import tempfile

from nuka.tasks import file
from nuka.tasks import virtualenv as venv

pytestmark = [
    pytest.mark.skipif(
        'python2' in os.environ['ENV_NAME'], reason='need a recent pip'),
]


@pytest.mark.asyncio
async def test_virtualenv_doc(host):
    res = await venv.virtualenv('/tmp/venv')
    assert res


@pytest.mark.asyncio
async def test_requirements(host, diff_mode):
    if await file.exists('/tmp/venv'):
        await file.rm('/tmp/venv')

    with diff_mode:
        res = await venv.virtualenv('/tmp/venv')
        assert '+/tmp/venv/bin/python' in res.res['diff'], res.res['diff']

    with tempfile.NamedTemporaryFile() as fd:
        fd.write(b'six')
        fd.flush()
        assert await venv.virtualenv('/tmp/venv', requirements=fd.name)

    with diff_mode:
        res = await venv.virtualenv('/tmp/venv')
        assert '+/tmp/venv/bin/python' not in res.res['diff'], res.res['diff']
