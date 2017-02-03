# -*- coding: utf-8 -*-
import pytest
from nuka.tasks import file
from nuka.tasks import user
from nuka.tasks import shell


@pytest.mark.asyncio
async def test_create_user(host, diff_mode):
    diff_mode(False)
    assert (await user.delete_user('test_user1'))

    with diff_mode:
        res = await user.delete_user(username='test_user1')
        assert '-test_user1' not in res.res['diff']

        res = await user.create_user(username='test_user1')
        assert '+test_user1' in res.res['diff']

    assert (await user.create_user(username='test_user1'))

    with diff_mode:
        res = await user.delete_user(username='test_user1')
        assert '-test_user1' in res.res['diff']

        res = await user.create_user(username='test_user1')
        assert '+test_user1' not in res.res['diff']

    assert (await user.delete_user('test_user1'))
    assert not (await file.exists('/home/test_user1'))
    assert (await user.create_user(username='test_user1'))
    assert (await file.exists('/home/test_user1'))
    res = await shell.shell(['whoami'], switch_user='test_user1')
    assert res.stdout.strip() == 'test_user1'

    assert (await user.delete_user('test_user1'))
    assert not (await file.exists('/home/test_user1'))


@pytest.mark.asyncio
async def test_create_user_doc(host):
    await user.create_user('myuser')


@pytest.mark.asyncio
async def test_authorized_keys_doc(host):
    await user.create_user('myuser')
    await user.authorized_keys(
        username='myuser', keysfile='~/.ssh/authorized_keys')


@pytest.mark.asyncio
async def test_delete_user_doc(host):
    await user.delete_user('myuser')
