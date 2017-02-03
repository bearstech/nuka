==================================================================
:mod:`nuka.tasks.file`
==================================================================

.. automodule:: nuka.tasks.file


nuka.tasks.file.cat
==================================================================

.. autofunction:: cat


Example:

.. code-block:: python

    res = await file.cat('/etc/default/useradd')
    assert res.content



nuka.tasks.file.chmod
==================================================================

.. autofunction:: chmod



nuka.tasks.file.exists
==================================================================

.. autofunction:: exists


Example:

.. code-block:: python

    res = await file.exists('/tmp')
    assert bool(res) is True

    res = await file.exists('/nope')
    assert bool(res) is False



nuka.tasks.file.mkdir
==================================================================

.. autofunction:: mkdir


Example:

.. code-block:: python

    if not await file.exists('/tmp/doc'):
        await file.mkdir('/tmp/doc')



nuka.tasks.file.put
==================================================================

.. autofunction:: put


Example:

.. code-block:: python

    await file.put([
        dict(src='/etc/resolv.conf', dst='/tmp/resolv.conf'),
        dict(src='docs/utils.py', dst='/tmp/utils.py', executable=True),
        dict(src='example.j2', dst='/tmp/xx1', mod='600'),
    ], ctx=dict(name='example'))



nuka.tasks.file.rm
==================================================================

.. autofunction:: rm


Example:

.. code-block:: python

    await file.rm('/tmp/doc')



nuka.tasks.file.scripts
==================================================================

.. autofunction:: scripts



nuka.tasks.file.update
==================================================================

.. autofunction:: update


Example:

.. code-block:: python

    await file.update(
        dst='/etc/default/useradd',
        replaces=[(r'^\# HOME=/home', 'HOME=/new_home')])


