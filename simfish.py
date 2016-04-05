#!/usr/bin/env python
# encoding:utf-8

from wsgiref.simple_server import make_server
import Cookie
import threading
import re
import cgi
import mimetypes
import time
import os
import functools


try:
    from urlparse import parse_qs
except ImportError:
    from cgi import parse_qs


TEMPLATE = os.getcwd()
STATIC = os.getcwd()

HTTP_CODES = {
    100: 'CONTINUE',
    101: 'SWITCHING PROTOCOLS',
    200: 'OK',
    201: 'CREATED',
    202: 'ACCEPTED',
    203: 'NON-AUTHORITATIVE INFORMATION',
    204: 'NO CONTENT',
    205: 'RESET CONTENT',
    206: 'PARTIAL CONTENT',
    300: 'MULTIPLE CHOICES',
    301: 'MOVED PERMANENTLY',
    302: 'FOUND',
    303: 'SEE OTHER',
    304: 'NOT MODIFIED',
    305: 'USE PROXY',
    306: 'RESERVED',
    307: 'TEMPORARY REDIRECT',
    400: 'BAD REQUEST',
    401: 'UNAUTHORIZED',
    402: 'PAYMENT REQUIRED',
    403: 'FORBIDDEN',
    404: 'NOT FOUND',
    405: 'METHOD NOT ALLOWED',
    406: 'NOT ACCEPTABLE',
    407: 'PROXY AUTHENTICATION REQUIRED',
    408: 'REQUEST TIMEOUT',
    409: 'CONFLICT',
    410: 'GONE',
    411: 'LENGTH REQUIRED',
    412: 'PRECONDITION FAILED',
    413: 'REQUEST ENTITY TOO LARGE',
    414: 'REQUEST-URI TOO LONG',
    415: 'UNSUPPORTED MEDIA TYPE',
    416: 'REQUESTED RANGE NOT SATISFIABLE',
    417: 'EXPECTATION FAILED',
    500: 'INTERNAL SERVER ERROR',
    501: 'NOT IMPLEMENTED',
    502: 'BAD GATEWAY',
    503: 'SERVICE UNAVAILABLE',
    504: 'GATEWAY TIMEOUT',
    505: 'HTTP VERSION NOT SUPPORTED',
}


# Header
class HeaderDict(dict):
    """ 
    A dictionary with case insensitive (titled) keys.
    You may add a list of strings to send multible headers with the same name.
    """

    def __setitem__(self, key, value):
        return dict.__setitem__(self, key.title(), value)

    def __getitem__(self, key):
        return dict.__getitem__(self, key.title())

    def __delitem__(self, key):
        return dict.__delitem__(self, key.title())

    def __contains__(self, key):
        return dict.__contains__(self, key.title())

    def items(self):
        """ Returns a list of (key, value) tuples """
        for key, values in dict.items(self):
            if not isinstance(values, list):
                values = [values]
            for value in values:
                yield (key, str(value))

    def add(self, key, value):
        """ Adds a new header without deleting old ones """

        if isinstance(value, list):
            for v in value:
                self.add(key, v)
        elif key in self:
            if isinstance(self[key], list):
                self[key].append(value)
            else:
                self[key] = [self[key], value]
        else:
            self[key] = [value]


# Exceptions
class SimfishException(Exception):
    """
    A base class for exception
    """
    pass


class HTTPError(SimfishException):
    """
    Jump out to error handler
    """

    def __init__(self, status, text):
        self.text = text
        self.http_status = status

    def __str__(self):
        return self.text


class BreakSimfish(SimfishException):
    """
    Jump out of execution
    """

    def __init__(self, text):
        self.text = text


# Route
class Routes:
    """
    FrameWork Routes
    """
    ROUTES = {}

    @classmethod
    def add(cls, url, handler):
        """add route and handler to ROUTES"""
        if not url.startswith('/'):
            url = '/' + url
        if re.match(r'/(\w+/)*\w*(\.\w+){0,1}$', url).group() == url:
            cls.ROUTES[url] = handler
        else:
            raise BreakSimfish("%s is not valid" % url)

    @classmethod
    def match(cls, url):
        """match url in ROUTES"""
        if not url:
            return None
        url = url.strip()
        return cls.ROUTES.get(url, None)

    @classmethod
    def load_urls(cls, urls):
        for item in urls:
            cls.add(item[0], item[1])


def route(url, **kargs):
    """Decorator for request handler. Same as Routes.route(url, handler)."""
    def wrapper(handler):
        Routes.add(url, handler, **kargs)
        return handler
    return wrapper


# Template
class BaseTemplate(object):
    def __init__(self, template='', filename='<template>'):
        self.source = filename
        if self.source != '<template>':
            fp = open(filename)
            template = fp.read()
            fp.close()
        self.parse(template)

    def parse(self, template):
        raise NotImplementedError

    def render(self, **args):
        raise NotImplementedError

    @classmethod
    def find(cls, name):
        files = ['/'.join([path, name]) for path in TEMPLATE if os.path.isfile('/'.join([path, name]))]
        if files:
            return cls(filename=files[0])
        else:
            raise Exception('Template not found: %s' % repr(name))


class SimpleTemplate(BaseTemplate):
    re_python = re.compile(
        r'^\s*%\s*(?:(if|elif|else|try|except|finally|for|while|with|def|class)|(include.*)|(end.*)|(.*))')
    re_inline = re.compile(r'\{\{(.*?)\}\}')
    dedent_keywords = ('elif', 'else', 'except', 'finally')

    def parse(self, template):
        indent = 0
        strbuffer = []
        code = []
        self.subtemplates = {}

        class PyStmt(str):
            def __repr__(self): return 'str(' + self + ')'

        def flush():
            if len(strbuffer):
                code.append(" " * indent + "stdout.append(%s)" % repr(''.join(strbuffer)))
                code.append("\n" * len(strbuffer))  # to preserve line numbers
                del strbuffer[:]

        for line in template.splitlines(True):
            m = self.re_python.match(line)
            if m:
                flush()
                keyword, include, end, statement = m.groups()
                if keyword:
                    if keyword in self.dedent_keywords:
                        indent -= 1
                    code.append(" " * indent + line[m.start(1):])
                    indent += 1
                elif include:
                    tmp = line[m.end(2):].strip().split(None, 1)
                    name = tmp[0]
                    args = tmp[1:] and tmp[1] or ''
                    self.subtemplates[name] = SimpleTemplate.find(name)
                    code.append(" " * indent + "stdout.append(_subtemplates[%s].render(%s))\n" % (repr(name), args))
                elif end:
                    indent -= 1
                    code.append(" " * indent + '#' + line[m.start(3):])
                elif statement:
                    code.append(" " * indent + line[m.start(4):])
            else:
                splits = self.re_inline.split(line)  # text, (expr, text)*
                if len(splits) == 1:
                    strbuffer.append(line)
                else:
                    flush()
                    for i in xrange(1, len(splits), 2):
                        splits[i] = PyStmt(splits[i])
                    code.append(" " * indent + "stdout.extend(%s)\n" % repr(splits))
        flush()
        self.co = compile("".join(code), self.source, 'exec')

    def render(self, **args):
        ''' Returns the rendered template using keyword arguments as local variables. '''
        args['stdout'] = []
        args['_subtemplates'] = self.subtemplates
        eval(self.co, args, globals())
        return ''.join(args['stdout']), "text/html"


# Request
class Request(threading.local):
    """
    Represents a single request using thread-local namespace
    """

    def bind(self, environ):
        """ Bind the enviroment """
        self._environ = environ
        self._GET = None
        self._POST = None
        self._COOKIES = None
        self.path = self._environ.get('PATH_INFO', '/').strip()
        if not self.path.startswith('/'):
            self.path = '/' + self.path

    @property
    def method(self):
        """ Returns the request method (GET,POST,PUT,DELETE,...) """
        return self._environ.get('REQUEST_METHOD', 'GET').upper()

    @property
    def query_string(self):
        """ Content of QUERY_STRING """
        return self._environ.get('QUERY_STRING', '')

    @property
    def GET(self):
        """ Returns a dict with GET parameters. """
        if self._GET is None:
            raw_dict = parse_qs(self.query_string, keep_blank_values=1)
            self._GET = {}
            for key, value in raw_dict.items():
                if len(value) == 1:
                    self._GET[key] = value[0]
                else:
                    self._GET[key] = value
        return self._GET

    @property
    def POST(self):
        """ Returns a dict with parsed POST data. """
        if self._POST is None:
            raw_data = cgi.FieldStorage(fp=self._environ['wsgi.input'], environ=self._environ)
            self._POST = {}
            if raw_data:
                for key, value in raw_data.items():
                    if isinstance(value, list):
                        self._POST[key] = [v.value for v in value]
                    elif value.filename:
                        self._POST[key] = value
                    else:
                        self._POST[key] = value.value
        return self._POST

    @property
    def COOKIES(self):
        """ Returns a dict with COOKIES. """
        if self._COOKIES is None:
            raw_dict = Cookie.SimpleCookie(self._environ.get('HTTP_COOKIE', ''))
            self._COOKIES = {}
            for cookie in raw_dict.values():
                self._COOKIES[cookie.key] = cookie.value
        return self._COOKIES


# Response
class Response(threading.local):
    """
    Represents a single response using thread-local namespace.
    """

    def bind(self):
        """ Clears old data and creates a brand new Response object """
        self._COOKIES = None
        self.status = 200
        self.header = HeaderDict()
        self.header['Content-type'] = 'text/plain'
        self.error = None

    @property
    def COOKIES(self):
        if not self._COOKIES:
            self._COOKIES = Cookie.SimpleCookie()
        return self._COOKIES

    def set_cookie(self, key, value, **kargs):
        """ 
        Sets a Cookie. Optional settings: expires, path, comment, 
        domain, max-age, secure, version, httponly 
        """
        self.COOKIES[key] = value
        for k in kargs:
            self.COOKIES[key][k] = kargs[k]


# The object of request and response 
request = Request()
response = Response()


# Redirect to another url
def redirect(url, code=307):
    """ Aborts execution and causes a 307 redirect """
    response.status = code
    response.header['Location'] = url
    raise SimfishException("")


# Send static or other files
def send_file(filename, root, mimetype=None, guessmime=True):
    """ Sends files """
    name = filename
    root = os.path.abspath(root) + '/'
    filename = os.path.normpath(filename).strip('/')
    filename = os.path.join(root, filename)

    if not filename.startswith(root):
        response.status = 401
        return "Access denied."
    if not os.path.exists(filename) or not os.path.isfile(filename):
        response.status = 404
        return "File does not exist."
    if not os.access(filename, os.R_OK):
        response.status = 401
        return "You do not have permission to access this file."

    if mimetype:
        response.header['Content-type'] = mimetype
    elif guessmime:
        guess = mimetypes.guess_type(filename)[0]
        if guess:
            response.header['Content-type'] = guess

    stats = os.stat(filename)
    # TODO: HTTP_IF_MODIFIED_SINCE -> 304 (Thu, 02 Jul 2009 23:16:31 CEST)
    if mimetype == 'application/octet-stream' \
        and "Content-Disposition" not in response.header:
        response.header["Content-Disposition"] = "attachment;filename=%s" % name
    elif 'Last-Modified' not in response.header:
        ts = time.gmtime(stats.st_mtime)
        ts = time.strftime("%a, %d %b %Y %H:%M:%S +0000", ts)
        response.header["Content-Length"] = stats.st_size
        response.header['Last-Modified'] = ts
    return open(filename, 'r')


class Simfish:
    def __init__(self, environ, start_response):
        self.environ = environ
        self.start = start_response
        request.bind(environ)
        response.bind()

    def __iter__(self):
        path = request.path
        handler = Routes.match(path)
        result = ""
        if not handler:
            response.status = 404
            result = "not Found"
        else:
            try:
                result = handler(request)
            except SimfishException, output:
                result = output
        if isinstance(result, tuple) and len(result) == 2:
            response.header['Content-type'] = result[1]
            result = result[0]
        status = '%d %s' % (response.status, HTTP_CODES[response.status])
        self.start(status, list(response.header.items()))

        if hasattr(result, 'read'):
            if 'wsgi.file_wrapper' in self.environ:
                return self.environ['wsgi.file_wrapper'](result)
            else:
                return iter(lambda: result.read(8192), '')
        elif isinstance(result, basestring):
            return iter([result])
        else:
            return iter(result)


class application:
    """Simfish is a small FrameWork"""

    def __init__(self, urls=None, port=8086):
        if urls:
            Routes.load_urls(urls)
        self.port = port

    def run(self):
        httpd = make_server('', self.port, Simfish)
        sa = httpd.socket.getsockname()
        print 'http://{0}:{1}/'.format(*sa)
        httpd.serve_forever()

