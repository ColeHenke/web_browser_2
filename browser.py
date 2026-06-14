import socket
import ssl
import tkinter
import tkinter.font

from typing import Literal

DATA_SCHEME = 'data:text/html,'
WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

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
        tokens = lex(body)

        self.display_list = Layout(tokens).display_list
        self.draw()

    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()

class Text:
    def __init__(self, text):
        self.text = text

class Tag:
    def __init__(self, tag):
        self.tag = tag

class Layout:
    def __init__(self, tokens):
        self.display_list = []
        self.cursor_x, self.cursor_y = HSTEP, VSTEP

        # some font attributes
        self.weight: Literal['normal', 'bold'] = 'normal'
        self.style: Literal['roman', 'italic'] = 'roman'
        self.size = 12

        for token in tokens:
            self.token(token)

    def token(self, token):
        if isinstance(token, Text):
            for word in token.text.split():
                self.word(word)
        elif token.tag == "i":
            self.style = "italic"
        elif token.tag == "/i":
            self.style = "roman"
        elif token.tag == "b":
            self.weight = "bold"
        elif token.tag == "/b":
            self.weight = "normal"
        elif token.tag == "small":
            self.size -= 2
        elif token.tag == "/small":
            self.size += 2
        elif token.tag == "big":
            self.size += 4
        elif token.tag == "/big":
            self.size -= 4

    def word(self, word):
        font = tkinter.font.Font(size=self.size, weight=self.weight, slant=self.style)
        w = font.measure(word)
        self.display_list.append((self.cursor_x, self.cursor_y, word, font))
        self.cursor_x += w + font.measure(' ')

        if self.cursor_x + w > WIDTH - HSTEP * 3:
            self.cursor_y += font.metrics('linespace') * 1.25
            self.cursor_x = HSTEP

def lex(body):
    buffer = ''
    out = []
    in_tag = False
    skip_chars = 0
    for i, c in enumerate(body):
        if skip_chars > 0:
            skip_chars -= 1
            continue
        if c == '<':
            in_tag = True
            if buffer: out.append(Text(buffer))
            buffer = ''
        elif c == '>':
            in_tag = False
            out.append(Tag(buffer))
            buffer = ''
        elif in_tag:
            buffer += c
        elif not in_tag:
            if c == '&':
                if body[i+1:i+4] == 'lt;':
                    c = '<'
                    skip_chars += 3
                elif body[i+1:i+4] == 'gt;':
                    c = '>'
                    skip_chars += 3
            buffer += c
    if not in_tag and buffer:
        out.append(Text(buffer))
    return out

if __name__ == "__main__":
    import sys
    Browser().load(Url(sys.argv[1]))
    tkinter.mainloop()