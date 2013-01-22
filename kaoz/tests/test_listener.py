# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

from .common import unittest, get_local_conf, configure_logger
import kaoz.listener
import Queue
import os
import socket

try:
    import ssl
    has_ssl = True
except ImportError:
    has_ssl = False

configure_logger(kaoz.listener.logger, 'WARNING')


class DummyPublisher(object):
    """Publisher for testing purpose"""

    def __init__(self):
        self.lines = Queue.Queue()

    def send_line(self, line):
        """Listener sends a line to the publisher"""
        self.lines.put(line)


def sslize_config(config):
    """Give a new configuration with SSL enabled for the listener"""
    config.set('listener', 'ssl', 'true')

    # Replace relative paths by absolute ones
    ssl_cert = config.get('listener', 'ssl_cert')
    if not ssl_cert or ssl_cert[0] != '/':
        ssl_cert = os.path.join(os.path.dirname(__file__), ssl_cert)
        config.set('listener', 'ssl_cert', ssl_cert)
    ssl_key = config.get('listener', 'ssl_key')
    if not ssl_key or ssl_key[0] != '/':
        ssl_key = os.path.join(os.path.dirname(__file__), ssl_key)
        config.set('listener', 'ssl_key', ssl_key)
    return config


class ListenerTestCase(unittest.TestCase):

    def setUp(self):
        self.config = get_local_conf()
        self.ssl_config = sslize_config(get_local_conf())
        self.host = self.config.get('listener', 'host')
        self.port = self.config.getint('listener', 'port')
        self.password = self.config.get('listener', 'password')
        self.pub = DummyPublisher()

    def tearDown(self):
        del self.pub

    def test_listener(self):
        sent_line = u"#chan1:Hello, world"
        # Start listener
        with kaoz.listener.TCPListener(self.pub, self.config):
            # Send one line
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            packet = u"%s:%s" % (self.password, sent_line)
            sock.sendall(packet.encode('UTF-8'))
            sock.close()

            # Close everything and wait for the publisher to receive the line
            try:
                received_line = self.pub.lines.get(timeout=2)
            except Queue.Empty:
                self.fail(u"Publisher didn't receive anything")
        self.assertEquals(received_line, sent_line)
        self.assertTrue(self.pub.lines.empty(), u"Too many published lines")

    def test_multiple_lines(self):
        sent_lines = map(lambda i: u"#chan%d:Line %d" % (i, i), range(10))
        packet = u"\r\n".join(map(lambda l: u"%s:%s" % (self.password, l),
                                  sent_lines))
        with kaoz.listener.TCPListener(self.pub, self.config):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            sock.sendall(packet.encode('UTF-8'))
            sock.close()
            try:
                for l in sent_lines:
                    rcvd_line = self.pub.lines.get(timeout=2)
                    self.assertEquals(rcvd_line, l, u"Wrong published line")
            except Queue.Empty:
                self.fail(u"Publisher didn't receive enough")
        self.assertTrue(self.pub.lines.empty(), u"Too many published lines")

    @unittest.skipUnless(has_ssl, "requires ssl library")
    def test_ssl(self):
        sent_line = u"#chan1:Hello, world, from SSL"
        # Start listener
        with kaoz.listener.TCPListener(self.pub, self.ssl_config):
            # Send one line
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock = ssl.wrap_socket(sock)
            sock.connect((self.host, self.port))
            packet = u"%s:%s" % (self.password, sent_line)
            sock.sendall(packet.encode('UTF-8'))
            sock.close()

            # Close everything and wait for the publisher to receive the line
            try:
                received_line = self.pub.lines.get(timeout=2)
            except Queue.Empty:
                self.fail(u"Publisher didn't receive anything")
        self.assertEquals(received_line, sent_line)
        self.assertTrue(self.pub.lines.empty(), u"Too many published lines")
