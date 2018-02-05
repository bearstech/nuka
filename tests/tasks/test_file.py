# -*- coding: utf-8 -*-
import jinja2
import pytest
import asyncio
from nuka.tasks import file


@pytest.mark.asyncio
async def test_cat_doc(host):
    res = await file.cat('/etc/default/useradd')
    assert res.content


@pytest.mark.asyncio
async def test_exists_doc(host):
    res = await file.exists('/tmp')
    assert bool(res) is True

    res = await file.exists('/nope')
    assert bool(res) is False


@pytest.mark.asyncio
async def test_mkdir_doc(host):
    if not await file.exists('/tmp/doc'):
        await file.mkdir('/tmp/doc')


@pytest.mark.asyncio
async def test_rm_doc(host):
    await file.rm('/tmp/doc')


@pytest.mark.asyncio
async def test_put_doc(host):
    await file.put([
        dict(src='/etc/resolv.conf', dst='/tmp/resolv.conf'),
        dict(src='docs/utils.py', dst='/tmp/utils.py', executable=True),
        # jinja2 template
        dict(src='example.j2', dst='/tmp/xx1', mod='600'),
        # symlink
        dict(linkto='/etc/hosts', dst='/etc/hosts2'),
    ], ctx=dict(name='example'))


@pytest.mark.asyncio
async def test_update_doc(host):
    await file.update(
        dst='/etc/default/useradd',
        replaces=[(r'^\# HOME=/home', 'HOME=/new_home')])


@pytest.mark.asyncio
async def test_mkdir_rmdir(host):
    res = await file.exists('/tmp/tox_test')
    assert bool(res) is False
    res = await file.mkdir(dst='/tmp/tox_test')
    assert bool(res)
    res = await file.exists(dst='/tmp/tox_test')
    assert bool(res)
    res = await file.rm(dst='/tmp/tox_test')
    assert bool(res)
    res = await file.exists(dst='/tmp/tox_test')
    assert bool(res) is False


@pytest.mark.asyncio
async def test_mkdir_rmdir_unauthorized(host, user):
    with pytest.raises(asyncio.CancelledError):
        await file.mkdir(dst='/etc/tox_test', switch_user=user)
    with pytest.raises(asyncio.CancelledError):
        await file.mkdir(dst='/var', switch_user=user)


@pytest.mark.asyncio
async def test_put(host):
    with open('/tmp/to_put.txt', 'wb') as fd:
        fd.write(b'yo')
    res = await file.put([dict(
        src='/tmp/to_put.txt', dst='/tmp/xx', executable=True
    )])
    assert bool(res)
    res = await file.cat('/tmp/xx')
    assert res.content == 'yo'


@pytest.mark.asyncio
async def test_put_with_user(host, user):
    with open('/tmp/to_put.txt', 'wb') as fd:
        fd.write(b'yo')
    res = await file.put([dict(
        src='/tmp/to_put.txt', dst='/tmp/test_' + user,
        )],
        switch_user=user)
    assert bool(res)
    res = await file.rm(dst='/tmp/test_' + user,
                        switch_user=user)
    assert bool(res)

    with pytest.raises(asyncio.CancelledError):
        await file.put([dict(src='/tmp/to_put.txt', dst='/etc/test_' + user)],
                       switch_user=user)


@pytest.mark.asyncio
async def test_scripts(host):
    hid = str(id(host))
    script = '#!/bin/bash\necho {0} > /tmp/h'.format(hid)
    with open('/tmp/to_put_script', 'wb') as fd:
        fd.write(script.encode('utf8'))
    res = await file.scripts([dict(
        src='/tmp/to_put_script', dst='/tmp/script'
    )])
    assert bool(res)

    res = await file.cat('/tmp/h')
    assert res.content.strip() == hid


@pytest.mark.asyncio
async def test_template(host):
    res = await file.put([
        dict(src='example.j2', dst='/tmp/xx0', executable=True),
        dict(src='example.j2', dst='/tmp/xx1', mod='600'),
        ],
        ctx=dict(name='dude'))
    assert bool(res)
    for i in range(0, 2):
        res = await file.cat('/tmp/xx{0}'.format(i))
        assert res.content == 'yo dude\n'


@pytest.mark.asyncio
async def test_template_error(host):
    with pytest.raises(jinja2.UndefinedError):
        await file.put([dict(src='error.j2', dst='/tmp/xx0')])


@pytest.mark.asyncio
async def test_update(host):
    res = await file.update(
        dst='/etc/default/useradd',
        replaces=[(r'^.*HOME=/home', 'HOME=/new_home')])
    assert bool(res)

    res = await file.cat('/etc/default/useradd')
    assert 'HOME=/new_home' in res.content

    res = await file.update(
        dst='/etc/default/useradd',
        replaces=[(r'HOME=/new_home', 'HOME=/home')])
    assert bool(res)

    res = await file.cat('/etc/default/useradd')
    assert 'HOME=/new_home' not in res.content


@pytest.mark.asyncio
async def test_mv(host):
    with open('/tmp/to_move.txt', 'wb') as fd:
        fd.write(b'yo')
    res = await file.put([dict(
        src='/tmp/to_move.txt', dst='/tmp/to_move.txt',
        )])
    res = await file.mv(src='/tmp/to_move.txt', dst='/tmp/moved.txt')
    assert bool(res)
    res = await file.cat('/tmp/moved.txt')
    assert res.content.strip() == 'yo'
