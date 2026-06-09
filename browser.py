import socket
from urllib import request


class Url:
    def __init__(self, url):
        self.scheme, url = url.split('://', 1)
        assert self.scheme == 'http'

        if '/' not in url:
            url += '/'
        self.host, url = url.split('/', 1)
        self.path = '/' + url

    def request(self):
        s = socket.socket(type=socket.AF_INET, family=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        s.connect((self.host, 80))

        request = 'GET {} HTTP/1.0\r\n'.format(self.path)
        request += 'Host: {}\r\n'.format(self.host)
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