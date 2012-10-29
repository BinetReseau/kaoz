# -*- coding: utf-8 -*-
# Copyright © 2011-2012 Binet Réseau
# See the LICENCE file for more informations

# This file is a part of Kaoz, a free irc notifier

import logging
import SocketServer
import threading

try:
    import ssl
    has_ssl = True
except ImportError:
    has_ssl = False

logger = logging.getLogger(__name__)


class TCPListenerHandler(SocketServer.BaseRequestHandler):
    """Manage a request from TCP listener module"""

    def setup(self):
        if self.server.use_ssl:
            real_sock = ssl.wrap_socket(self.request,
                                        keyfile=self.server.ssl_keyfile,
                                        certfile=self.server.ssl_certfile,
                                        server_side=True,
                                        do_handshake_on_connect=True)
            real_sock.settimeout(0.5)
        else:
            real_sock = self.request
        self.rfile = real_sock.makefile('r')

    def handle(self):
        for line in self.rfile:
            line = line.strip()
            if line:
                logger.debug(u"Received line %s" % line)
                self.server.publisher.send_line(line)


class TCPListener(threading.Thread):
    """Thread to manage a TCP server (listener)"""

    def __init__(self, publisher, config):
        super(TCPListener, self).__init__()
        self._host = config.get('listener', 'host')
        self._port = config.getint('listener', 'port')
        self._server = SocketServer.TCPServer((self._host, self._port),
            TCPListenerHandler)
        if config.getboolean('irc', 'ssl'):
            assert has_ssl, "SSL support requested but not available"
            self._server.use_ssl = True
            self._server.ssl_keyfile = config.get('listener', 'ssl_cert')
            self._server.ssl_certfile = config.get('listener', 'ssl_cert')
        else:
            self._server.use_ssl = False
        self._server.publisher = publisher

    def run(self):
        self._server.serve_forever()
