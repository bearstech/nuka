# -*- coding: utf-8 -*-
import pytest
from nuka import reports
from nuka.tasks.shell import command


@pytest.mark.asyncio
async def test_reports(host):
    await command(['ls'])
    reports.build_reports([host])
