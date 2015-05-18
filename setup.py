#!/usr/bin/env python
#-*- coding:utf-8 -*-

import sys
import os
try:
	from setuptools import setup
except ImportError:
	from distutils.core import setup  

import simfish

setup(
	name="simfish",
	version="0.10",
	description="a simple web framework",
	author="Yu Xianda",
	author_email='xianda_yu@outlook.com',
	url="http://cnblogs.com/coder2012/",
	license="MIT",
	scripts=["simfish.py"],
	py_modules=['simfish'],
)
