import socket
import ssl
import tkinter

DATA_SCHEME = 'data:text/html,'
WIDTH, HEIGHT = 800, 600

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

        print(self.scheme)
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

    def load(self, url):
        HSTEP, VSTEP = 13, 18
        cursor_x, cursor_y = HSTEP, VSTEP

        body = url.request()
        text = lex(body)
        for c in text:
            self.canvas.create_text(cursor_x, cursor_y, text=c)
            cursor_x += HSTEP

            if cursor_x > WIDTH - HSTEP:
                cursor_y += VSTEP
                cursor_x = HSTEP



def lex(body):
    text =''
    in_tag = False
    skip_chars = 0
    for i, c in enumerate(body):
        if skip_chars > 0:
            skip_chars -= 1
            continue
        if c == '<':
            in_tag = True
        elif c == '>':
            in_tag = False
        elif not in_tag:
            if c == '&':
                if body[i+1:i+4] == 'lt;':
                    c = '<'
                    skip_chars += 3
                elif body[i+1:i+4] == 'gt;':
                    c = '>'
                    skip_chars += 3
            text += c

    return text

if __name__ == "__main__":
    import sys
    Browser().load(Url(sys.argv[1]))
    tkinter.mainloop()