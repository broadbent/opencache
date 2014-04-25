#!/usr/bin/env python2.7

from setuptools import setup

conf = dict(
    name='opencache',
    version='0.0.1-dev',
    description='An experimental HTTP caching platform utilising Software Defined Networking technology.',
    long_description='For more details and the README, please see our `GitHub page <https://github.com/broadbent/opencache>`_.',
    author='Matthew Broadbent',
    author_email='matt@matthewbroadbent.net',
    packages=['opencache', 'opencache.lib', 'opencache.controller', 'opencache.node',
    'opencache.node.server', 'opencache.controller.api', 'opencache.controller.request',
    'opencache.controller.state'],
    scripts=['scripts/opencache'],
    install_requires=['pymongo', 'pyzmq', 'configparser'],
    url='https://github.com/broadbent/opencache',
    license='Apache License, Version 2.0',
    download_url='https://github.com/broadbent/opencache/archive/0.0.1-dev.zip',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: DFSG approved',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: System :: Networking',
        'Topic :: System :: Distributed Computing',
        'Topic :: System :: Logging',
        'Topic :: System :: Monitoring'
        ]
)

setup(**conf)
