# -*- coding: utf-8 -*-
import os
from setuptools import setup
from setuptools import find_packages

version = '0.3'


def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()


docker = ['docker-compose']
cloud = ['python-novaclient', 'apache-libcloud', 'PyCrypto']
test = ['pytest', 'pytest-asyncio', 'coverage']
full = ['ujson'] + docker + cloud + test


setup(
    name='nuka',
    version=version,
    description="provisioning tool focused on performance.",
    long_description=read('README.rst'),
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.5',
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        ('License :: OSI Approved :: '
         'GNU General Public License v3 or later (GPLv3+)'),
        'Operating System :: POSIX',
        'Topic :: System :: Systems Administration',
    ],
    keywords='devops docker vagrant gce',
    license='GPLv3',
    author='Bearstech',
    author_email='py@bearstech.com',
    packages=find_packages(exclude=['docs', 'tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'pyaml',
        'jinja2',
        'uvloop',
        'asyncssh',
    ],
    extras_require={
        'full': ['tox'] + full,
        'speedup': ['ujson'],
        'docker': docker,
        'cloud': cloud,
        'test': full,
    },
    entry_points="""
    [pytest11]
    nuka = pytest_nuka
    """,
)
