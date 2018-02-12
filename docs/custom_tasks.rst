Use your own tasks
==================

nuka's tasks are just python class that inherit from :class:`nuka.task.Task`.

Here is a simple example:

.. literalinclude:: ../examples/tasks/timezone.py

You must be sure that your code is compatible with the python binaries you use
locally and remotely (2.x vs 3.x).

nuka's builtin tasks support python 2.7 and 3.4+

As a good practice your task should be isolated in a tasks package and must
only use python's stdlib.

Once it's done, you can use it:

.. literalinclude:: ../examples/tz.py
