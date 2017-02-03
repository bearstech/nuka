==================================================================
:mod:`nuka.tasks.user`
==================================================================

.. automodule:: nuka.tasks.user


nuka.tasks.user.authorized_keys
==================================================================

.. autofunction:: authorized_keys


Example:

.. code-block:: python

    await user.create_user('myuser')
    await user.authorized_keys(
        username='myuser', keysfile='~/.ssh/authorized_keys')



nuka.tasks.user.create_user
==================================================================

.. autofunction:: create_user


Example:

.. code-block:: python

    await user.create_user('myuser')



nuka.tasks.user.create_www_user
==================================================================

.. autofunction:: create_www_user



nuka.tasks.user.delete_user
==================================================================

.. autofunction:: delete_user


Example:

.. code-block:: python

    await user.delete_user('myuser')


