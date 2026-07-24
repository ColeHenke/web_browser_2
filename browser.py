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

BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
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
        self.canvas.delete("all")
        for cmd in self.display_list:
            if cmd.top > self.scroll + HEIGHT: continue
            if cmd.bottom < self.scroll: continue
            cmd.execute(self.scroll, self.canvas)

    def load(self, url):
        body = url.request()
        self.nodes = HtmlParser(body).parse()
        print_tree(self.nodes)
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)
        self.draw()

    def scrolldown(self, e):
        max_y = max(self.document.height + 2 * VSTEP - HEIGHT, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
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

class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.display_list = []

    def layout(self):
        self.x = self.parent.x
        self.width = self.parent.width

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        mode = self.layout_mode()
        if mode == "block":
            previous = None
            for child in self.node.children:
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next
        else:
            self.cursor_x = 0
            self.cursor_y = 0
            self.weight = "normal"
            self.style = "roman"
            self.size = 12

            self.line = []
            self.recurse(self.node)
            self.flush()

        for child in self.children:
            child.layout()

        if mode == "block":
            self.height = sum([
                child.height for child in self.children])
        else:
            self.height = self.cursor_y

    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and child.tag in BLOCK_ELEMENTS for child in self.node.children]):
            return "block"
        elif self.node.children:
            return "inline"
        else:
            return "block"

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

        if self.cursor_x + w > self.width:
            self.flush()

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max(metric['ascent'] for metric in metrics)

        baseline = self.cursor_y + max_ascent * 1.25

        for rel_x, word, font in self.line:
            x = rel_x + self.x
            y = self.y + baseline - font.metrics('ascent')
            self.display_list.append((x, y, word, font))

        max_descent = max(metric['descent'] for metric in metrics)
        self.cursor_y = baseline + max_descent * 1.25
        self.cursor_x = 0
        self.line = []

    def paint(self):
        cmds = []
        if self.layout_mode() == 'inline':
            if isinstance(self.node, Element) and self.node.tag == "pre":
                x2, y2 = self.x + self.width, self.y + self.height
                rect = DrawRect(self.x, self.y, x2, y2, "gray")
                cmds.append(rect)
            for x, y, word, font in self.display_list:
                cmds.append(DrawText(x, y, word, font))
        return cmds


class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []

        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        child.layout()
        self.height = child.height

    def paint(self):
        return []


class HtmlParser:
    HEAD_TAGS = ["base", "basefont", "bgsound", "noscript",
                 "link", "meta", "title", "style", "script"]

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
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"): return
        self.implicit_tags(tag)
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
        if not self.unfinished:
            self.implicit_tags(None)
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()

    def implicit_tags(self, tag):
        while True:
            open_tags = [node for node in self.unfinished]
            if open_tags == [] and tag != 'html':
                self.add_tag('html')
            elif open_tags == ['html'] and tag not in ['head', 'body', '/html']:
                if tag in self.HEAD_TAGS:
                    self.add_tag('head')
            elif open_tags == ["html", "head"] and \
                    tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            else: break


class DrawText:
    def __init__(self, x1, y1, text, font):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            anchor='nw')


class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width=0,
            fill=self.color)


class CSSParser:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception("Parsing error")
        return self.s[start:self.i]

    def literal(self, literal):
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception("Parsing error")
        self.i += 1

    def pair(self):
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.casefold(), val

    def body(self):
        pairs = {}
        while self.i < len(self.s):
            try:
                prop, val = self.pair()
                pairs[prop] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except Exception:
                why = self.ignore_until([";"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs

    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None

def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)


if __name__ == "__main__":
    import sys
    Browser().load(Url(sys.argv[1]))
    tkinter.mainloop()