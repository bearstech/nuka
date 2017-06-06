# -*- coding: utf-8 -*-
from nuka import utils


def test_json():
    assert utils.proto_loads_std(
        b'Content-type: plain\nContent-Length: 2\n{}') == {}
