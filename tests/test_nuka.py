# -*- coding: utf-8 -*-
import nuka


def test_event():
    e = nuka.Event('one')
    e.set_result(rc=1)
    assert e.res['rc'] == 1

    e = nuka.Event('two')
    e.release()
    assert e.done()

    e = nuka.Event('three')
    assert '<Event three' in repr(e)
