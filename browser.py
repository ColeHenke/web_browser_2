import socket
import ssl
import tkinter
import tkinter.font

from typing import Literal

DATA_SCHEME = 'data:text/html,'
WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

# 'void' tags
SELF_CLOSING_TAGS = [
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
]

# global font cache
FONTS = {}

# get font from cache or create new one
def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight,
            slant=style)
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]

class Url:
    def __init__(self, url):

        if '://' in url:
            self.scheme, url = url.split('://', 1)
            assert self.scheme in ['http', 'https']

            if self.scheme == 'https':
                self.port = 443
            elif self.scheme == 'http':
                self.port = 80

            if '/' not in url:
                url += '/'
            self.host, url = url.split('/', 1)
            self.path = '/' + url

            if ':' in self.host:
                self.host, port = self.host.split(':', 1)
                self.port = int(port)

        elif url.startswith(DATA_SCHEME):
            self.scheme, delim, self.content = url.partition(DATA_SCHEME)
            assert delim == DATA_SCHEME
            self.scheme += delim

    def request(self):
        if self.scheme == DATA_SCHEME:
            return '<body>{}</body>\r\n'.format(self.content)

        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        s.connect((self.host, self.port))

        if self.scheme == 'https':
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)

        request = 'GET {} HTTP/1.0\r\n'.format(self.path)
        request += 'Host: {}\r\n'.format(self.host)
        request += 'Connection: close\r\n'
        request += 'User-Agent: supa-browsa\r\n'
        request += '\r\n'
        s.send(request.encode())

        response = s.makefile('r', encoding='utf-8', newline='\r\n')

        statuline = response.readline()
        version, status, message = statuline.split(' ', 2)

        headers = {}
        while True:
            line = response.readline()
            if line == '\r\n':
                break
            header, value = line.split(':', 1)
            headers[header.casefold()] = value.strip()

        assert 'transfer-encoding' not in headers
        assert 'content-encoding' not in headers

        content = response.read()
        s.close()
        return content


class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.canvas.pack()
        self.display_list = []
        self.scroll = 0

        # binds
        self.window.bind("<Down>", self.scrolldown)

    def draw(self):
        self.canvas.delete('all')
        for x, y, c, font in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=c, anchor='nw', font=font)

    def load(self, url):
        body = url.request()
        self.nodes = HtmlParser(body).parse()
        print_tree(self.nodes)
        self.display_list = Layout(self.nodes).display_list
        self.draw()

    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()

class Text:
    def __init__(self, text, parent=None):
        self.text = text
        self.parent = parent
        self.children = []

    def __repr__(self):
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent=None):
        self.tag = tag
        self.attributes = attributes
        self.parent = parent
        self.children = []

    def __repr__(self):
        return "<" + self.tag + ">"

def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)

class Layout:
    def __init__(self, nodes):
        self.display_list = []
        self.cursor_x, self.cursor_y = HSTEP, VSTEP
        self.line = []

        # some font attributes
        self.weight: Literal['normal', 'bold'] = 'normal'
        self.style: Literal['roman', 'italic'] = 'roman'
        self.size = 12

        self.recurse(nodes)

        self.flush()

    def token(self, token):
        if isinstance(token, Text):
            for word in token.text.split():
                self.word(word)

    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "br":
            self.flush()


    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP

    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(' ')

        if self.cursor_x + w > WIDTH - HSTEP * 3:
            self.flush()

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max(metric['ascent'] for metric in metrics)

        baseline = self.cursor_y + max_ascent * 1.25

        for x, word, font in self.line:
            y = baseline - font.metrics('ascent')
            self.display_list.append((x, y, word, font))

        max_descent = max(metric['descent'] for metric in metrics)
        self.cursor_y = baseline + max_descent * 1.25
        self.cursor_x = HSTEP
        self.line = []


class HtmlParser:
    def __init__(self, body):
        self.unfinished = []
        self.body = body

    def parse(self):
        text = ''
        in_tag = False
        for c in self.body:
            if c == '<':
                in_tag = True
                if text:
                    self.add_text(text)
                    text = ''
            elif c == '>':
                in_tag = False
                self.add_tag(text)
                text = ''
            else:
                text += c
        if not in_tag and text:
            self.add_text(text)
        return self.finish()

    def add_text(self, text):
        if text.isspace(): return
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        if tag.startswith("!"): return
        tag, attributes = self.get_attributes(tag)
        if tag.startswith('/'):
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, parent)
            self.unfinished.append(node)

    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}
        for attribute_pair in parts[1:]:
            if '=' in attribute_pair:
                key, value = attribute_pair.split('=', 1)
                attributes[key.casefold()] = value.strip('"\'')
            else:
                attributes[attribute_pair.casefold()] = ''
        return tag, attributes

    def finish(self):
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()


if __name__ == "__main__":
    import sys
    Browser().load(Url(sys.argv[1]))
    tkinter.mainloop()