import socket
import urllib.parse
import random

from pip._internal.network import session

ENTRIES = [ 'Pavel was here' ]

SESSIONS = {}

def handle_connection(conx):
    req = conx.makefile("b")
    reqline = req.readline().decode('utf8')
    method, url, version = reqline.split(" ", 2)
    assert method in ["GET", "POST"]

    # read headers and store them in a dict
    headers = {}
    while True:
        line = req.readline().decode('utf8')
        if line == '\r\n': break
        header, value = line.split(":", 1)
        headers[header.casefold()] = value.strip()

    if "cookie" in headers:
        token = headers["cookie"][len("token="):]
    else:
        token = str(random.random())[2:]

    if 'content-length' in headers:
        length = int(headers['content-length'])
        body = req.read(length).decode('utf8')
    else:
        body = None

    session = SESSIONS.setdefault(token, {})
    status, body = do_request(session, method, url, headers, body)

    # send the page back to the browser
    response = "HTTP/1.0 {}\r\n".format(status)
    if "cookie" not in headers:
        template = "Set-Cookie: token={}\r\n"
        response += template.format(token)
    response += "Content-Length: {}\r\n".format(
        len(body.encode("utf8")))
    response += "\r\n" + body
    conx.send(response.encode('utf8'))
    conx.close()

def show_comments(session):
    out = "<!doctype html>"
    for entry in ENTRIES:
        out += "<p>" + entry + "</p>"

    out += "<form action=add method=post>"
    out += "<p><input name=guest></p>"
    out += "<p><button>Sign the book!</button></p>"
    out += "</form>"

    out += "<strong></strong>"
    out += "<script src=/comment.js></script>"
    return out

def add_entry(session, params):
    if 'guest' in params and len(params['guest']) <= 10:
        ENTRIES.append(params['guest'])
    return show_comments()

def do_request(session, method, url, headers, body):
    if method == "GET" and url == "/":
        return "200 OK", show_comments(session)
    elif method == "POST" and url == "/add":
        params = form_decode(body)
        add_entry(session, params)
        return "200 OK", show_comments(session)
    elif method == "GET" and url == "/comment.js":
        with open("comment.js") as f:
            return "200 OK", f.read()
    
    else:
        return "404 Not Found", not_found(url, method)

def form_decode(body):
    params = {}
    for field in body.split("&"):
        name, value = field.split("=", 1)
        name = urllib.parse.unquote_plus(name)
        value = urllib.parse.unquote_plus(value)
        params[name] = value
    return params

def not_found(url, method):
    out = "<!doctype html>"
    out += "<h1>{} {} not found!</h1>".format(method, url)
    return out

s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # immediately reuse the port on fail

s.bind(('', 8000))
s.listen()

while True:
    conx, addr = s.accept()
    handle_connection(conx)