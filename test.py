#!/usr/bin/env python
# encoding:utf8

from simfish import application, route, SimpleTemplate


@route('/index.html')
def index(request):
	return SimpleTemplate(filename="index.html").render()


@route('/')
def hello(request):
    return "hello world"


app = application(port=8086)
app.run()
