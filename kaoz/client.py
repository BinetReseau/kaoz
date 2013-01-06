# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

# This file is a part of Kaoz, a free irc notifier

import kaoz
import optparse
import socket
import sys

try:
    import ssl
    has_ssl = True
except ImportError:
    has_ssl = False


class Client:
    """Kaoz client"""

    def __init__(self, host, port, password, use_ssl=False, ssl_cert=None):
        self._password = password
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((host, port))
        if use_ssl:
            assert has_ssl, "SSL support requested but not available"
            self._sock = ssl.wrap_socket(self._sock, certfile=ssl_cert)

    def close(self):
        self._sock.close()

    def send_line(self, line, channel):
        assert channel, "No channel specified"
        self._sock.sendall('%s:%s:%s' % (self._password, channel, line))


def main():
    parser = optparse.OptionParser(
        usage="usage: %prog HOSTNAME PORT PASSWORD CHANNEL [options]",
        version="%prog " + kaoz.__version__)
    parser.add_option('-s', '--ssl', action='store_true', dest='use_ssl',
        help="Use SSL", default=False)
    parser.add_option('-c', '--cert', dest='ssl_cert',
        help="SSL certificate")
    parser.add_option('-m', '--message', dest='message',
        help="Send message instead of reading standard input", default=None)

    opts, args = parser.parse_args()
    if len(args) != 4:
        parser.error("Invalid number of arguments: %d != 4" % len(args))

    host, port, password, channel = args
    port = int(port)
    if not host or not port:
        parser.error("Invalid Host:port")
    if not channel:
        parser.error("Empty channel")

    client = Client(host, port, password,
                    use_ssl=opts.use_ssl, ssl_cert=opts.ssl_cert)
    if opts.message:
        client.send_line(opts.message, channel)
    else:
        for line in sys.stdin:
            client.send_line(line, channel)
    client.close()

if __name__ == '__main__':
    main()
