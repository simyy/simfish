# simfish

`simfish` is a fast, simple web framework for Python.

## How to use
```
#!/usr/bin/env python
# encoding:utf8

from simfish import application, route

@route('/')
def hello(request):
    return "hello world"

app = application(port=8086)
app.run()
```

### callback function

* a param of request, which it contains all infos in a http request;
```
def hello(request):
    return "hello world"
```
* return a string, or a string and a "content-type", "content-type" default is "text/plain".
```
def hello(request):
    return "<h1>hello world</h1>", "text/html"
```

### routing

* @route('xx/xx/') is a  decorator to mapping a callback function;
```
@route('/')
def hello(request):
    return "hello world"
```
* Routes.add("xxx", func) is also can add a maping;
```
Routes.add('/', hello)
```
* as a param for application, urls=[('url', func,),] also can work.
```
urls = [
  ('/', hello),
]
```

> suggest use last method, it is simple for others.

### get post and data
* method of get or post
```
def hello(request):
    return "hello world, method is %s"%request.method
```
* get or post data
```
def hello(request):
    param = request.GET.get("name", "")
    #param1 = request.POST.get("score", "")
    return "hello world"
```

### template

The template is a simple one, which is a default module in [bottle](link:http://www.bottlepy.org/docs/dev/tutorial.html#templates).
```
def tmpl(request):
    s = SimpleTemplate(template="<h1>hello world</h1>")
    return s.render()
    
def tmpl(request):
    s = SimpleTemplate(filename="index.html")
    return s.render()
```

### send file
```
from simfish import send_file

def file(request):
    return send_file('filename', 'path', mimetype="application/octet-stream")
```

### template and static path

set template and static path, or defualt is /yourproject/.
```
TEMPLATE = '/yourproject/tempates'
STATIC = '/yourproject/static'
```
