Contribute
==========

Feel free to clone the project on `GitHub <https://github.com/bearstech/nuka>`_.

Once you made a change, try to add a test for your feature/fix. At least assume
that you have'nt broke anything by running tox::

    $ tox
    ...
    py35-nukai-centos-7-python2-testing: commands succeeded
    py35-nukai-debian-wheezy-python2-testing: commands succeeded
    py35-nukai-debian-jessie-python2-testing: commands succeeded
    py35-nukai-debian-jessie-python3-testing: commands succeeded
    py35-nukai-debian-stretch-python2-testing: commands succeeded
    py35-nukai-debian-stretch-python3-testing: commands succeeded
    coverage: commands succeeded
    flake8: commands succeeded
    congratulations :)

 You can run tests for a specific version::

    $ tox -e py35-nukai-debian-stretch-python3-testing

You can also build the docs with::

    $ tox -e docs

And check the result::

    $ firefox .tox/docs/tmp/html/index.html
