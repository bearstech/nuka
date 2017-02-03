=============
Installation
=============

You'll need `python3.5+`.

Install python3.5 using pyenv
==============================

You can install python3.5 using `pyenv <https://github.com/yyuu/pyenv/>`_

You may need a few packages::

    $ sudo apt-get install build-essential libssl-dev libreadline-dev libbz2-dev python-virtualenv

Install pyenv::

    $ git clone https://github.com/yyuu/pyenv.git ~/.pyenv

Then install python3.5 (or python3.6)::

    $ ~/pyenv/bin/pyenv install 3.5.3

Install nuka in a virtualenv
=============================

Basic install::

    $ virtualenv -p $(which python3.5) myproject
    $ cd myproject
    $ source bin/activate

Check that your virtualenv use the correct version::

    $ bin/python --version
    Python 3.5.3

Install nuka in your virtualenv using pip::

    $ pip install nuka

If you're planning to use libcloud or docker then you'll need some extra
dependencies. Replace the last line by::

    $ pip install "nuka[full]"


Installing from source
======================

::

    $ pip install -e "git+https://github.com/bearstech/nuka.git#egg=nuka[full]"

Installing docker
=================

You should have a recent docker version. See `Install docker
<https://docs.docker.com/engine/installation/>`_
