#!/usr/bin/env python

from distutils.core import setup

setup(name='EchoMsg',
	version='0.1.6',
	description='Message generator for echolib.',
	author='Luka Cehovin',
	author_email='luka.cehovin@gmail.com',
	url='https://github.com/vicoslab/echomsg/',
	packages=['echomsg', 'echomsg.templates', 'echomsg.messages'],
	scripts=["bin/echogen"],
    requires=['pyparsing', 'jinja2', 'six'],
    package_data={'echomsg.templates': ['*.tpl'], 'echomsg.messages': ['*.msg']}
)
