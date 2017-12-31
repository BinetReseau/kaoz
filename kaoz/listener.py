# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

# This file is a part of Kaoz, a free irc notifier

import logging
import sys
import threading
import traceback

if sys.version_info < (3,):
    import SocketServer as socketserver
else:
    import socketserver

try:
    import ssl
    has_ssl = True
except ImportError:
    has_ssl = False

logger = logging.getLogger(__name__)


class TCPListenerHandler(socketserver.BaseRequestHandler):
    """Manage a request from TCP listener module"""

    def setup(self):
        self.real_sock = None
        if self.server.use_ssl:
            try:
                self.real_sock = ssl.wrap_socket(
                    self.request,
                    keyfile=self.server.ssl_keyfile,
                    certfile=self.server.ssl_certfile,
                    server_side=True,
                    do_handshake_on_connect=True)
                self.real_sock.settimeout(0.5)
                self.rfile = self.real_sock.makefile('rwb')
            except Exception:
                logger.error(traceback.format_exc().splitlines()[-1])
                self.rfile = None
                return
        else:
            self.rfile = self.request.makefile('rwb')

    def finish(self):
        if self.rfile is not None:
            self.rfile.close()
        if self.real_sock is not None:
            self.real_sock.close()

    def handle(self):
        if self.rfile is None:
            return
        client_addr = '%s:%d' % self.client_address
        logger.debug("Client connected from %s" % client_addr)
        for line in self.rfile:
            line = line.decode('utf-8')
            resp = self.handle_line(line)
            if resp is not None:
                resp += '\n'
                resp = resp.encode('utf-8')
                self.rfile.write(resp)
        logger.debug("Client disconnected from %s" % client_addr)

    def handle_line(self, line):
        """Remove 'password:' prefix of the incomming line"""
        line = line.strip()
        if not line:
            return
        expected_prefix = self.server.password + ':'
        if not line.startswith(expected_prefix):
            logger.warning("Invalid password on line %s" % line)
            return
        line = line[len(expected_prefix):]
        logger.debug("Received line %s" % line)
        if line[0] == ':':
            line = line[1:]
            return self.process_line(line)
        else:
            return self.publish_line(line)

    def process_line(self, line):
        """Process a command"""
        if line == 'channels':
            return str('\n'.join(self.server.publisher.channels()))
        else:
            return "Unknown command: %s" % line

    def publish_line(self, line):
        """Transmit received line to the publisher"""
        self.server.publisher.send_line(line)


class TCPListener(threading.Thread):
    """Thread to manage a TCP server (listener)"""

    def __init__(self, publisher, config, event=None):
        """ Initialise a TCP server depending on the configuration and
        optionally set an event when the thread ends.
        """
        super(TCPListener, self).__init__()
        self._host = config.get('listener', 'host')
        self._port = config.getint('listener', 'port')
        self._server = socketserver.ThreadingTCPServer(
            (self._host, self._port),
            TCPListenerHandler)
        self._server.password = config.get('listener', 'password')
        if config.getboolean('listener', 'ssl'):
            assert has_ssl, "SSL support requested but not available"
            self._server.use_ssl = True
            self._server.ssl_keyfile = config.get('listener', 'ssl_key')
            self._server.ssl_certfile = config.get('listener', 'ssl_cert')
        else:
            self._server.use_ssl = False
        self._server.publisher = publisher
        self._event = event

    def run(self):
        try:
            logger.debug("Server runs")
            self._server.serve_forever()
        except Exception:
            logger.critical(traceback.format_exc().splitlines()[-1])
        finally:
            logger.debug("Server has been shut down")
            if self._event:
                self._event.set()

    def stop(self):
        """Shut down listener"""
        self._server.shutdown()
        self._server.server_close()
        self.join()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
