import socket

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
        s.connect(self.host, 80)
