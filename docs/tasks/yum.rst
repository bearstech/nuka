==================================================================
:mod:`nuka.tasks.yum`
==================================================================

.. automodule:: nuka.tasks.yum


nuka.tasks.yum.install
==================================================================

.. autofunction:: install


Example:

.. code-block:: python

    res = await yum.install(['python'])
    assert bool(res)



nuka.tasks.yum.update
==================================================================

.. autofunction:: update


Example:

.. code-block:: python

    res = await yum.update(cache=3600)
    assert bool(res)


