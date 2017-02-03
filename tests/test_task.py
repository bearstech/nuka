# -*- coding: utf-8 -*-
import pytest

from nuka.task import Task


@pytest.mark.asyncio
async def test_error(host):

    class ErrTask(Task):
        def pre_process(self):
            raise OSError()

    with pytest.raises(OSError):
        await ErrTask()
