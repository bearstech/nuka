================================
nuka - a provisioning tool
================================

.. image:: https://travis-ci.org/bearstech/nuka.png?branch=master
  :target: https://travis-ci.org/bearstech/nuka

Because ops can dev.

nuka is a provisioning tool focused on performance. It massively uses Asyncio and SSH.
It is compatible with docker vagrant and apache-libcloud.


Quickstart
==========

Install nuka (See `Installation <https://doc.bearstech.com/nuka/install.html>`_
for detailled steps)::

    $ pip install "nuka[full]"

Then start a script:

.. literalinclude:: ../examples/quickstart.py

Run it using::

    $ chmod +x your_file.py
    $ ./your_file.py -v

The first run will be slow because we have to pull the docker image.
The next run will take approximately 1s.

Get some help::

    $ ./your_file.py -h

Look at the generated gantt of your deployement::

    $ firefox .nuka/reports/your_file_gantt.html

You'll get a dynamic report like this screenshot:

.. image:: https://doc.bearstech.com/nuka/_images/gantt.png
   :align: center

Index
=====

.. toctree::
   :maxdepth: 1
   :glob:

   install
   api
   tasks
   custom_tasks
   examples



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
