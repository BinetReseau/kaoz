# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

import kaoz.listener
import os
import socket
import sys

from .common import unittest, get_local_conf, configure_logger

if sys.version_info < (3,):
    import Queue as queue
else:
    import queue

try:
    import ssl
    has_ssl = True
except ImportError:
    has_ssl = False

configure_logger(kaoz.listener.logger, 'WARNING')


class DummyPublisher(object):
    """Publisher for testing purpose"""

    def __init__(self):
        self.lines = queue.Queue()
        self._channels = None

    def send_line(self, line):
        """Listener sends a line to the publisher"""
        self.lines.put(line)

    def channels(self, new_channel=None):
        if new_channel is not None:
            self._channels = new_channel
        return self._channels


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
        sent_line = "#chan1:Hello, world"
        # Start listener
        with kaoz.listener.TCPListener(self.pub, self.config):
            # Send one line
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            packet = "%s:%s" % (self.password, sent_line)
            sock.sendall(packet.encode('UTF-8'))
            sock.close()

            # Close everything and wait for the publisher to receive the line
            try:
                received_line = self.pub.lines.get(timeout=2)
            except queue.Empty:
                self.fail("Publisher didn't receive anything")
        self.assertEqual(received_line, sent_line)
        self.assertTrue(self.pub.lines.empty(), "Too many published lines")

    def test_multiple_lines(self):
        sent_lines = ["#chan%d:Line %d" % (i, i) for i in range(10)]
        packet = "\r\n".join([(self.password + ":" + l) for l in sent_lines])
        with kaoz.listener.TCPListener(self.pub, self.config):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            sock.sendall(packet.encode('UTF-8'))
            sock.close()
            try:
                for l in sent_lines:
                    rcvd_line = self.pub.lines.get(timeout=2)
                    self.assertEqual(rcvd_line, l, "Wrong published line")
            except queue.Empty:
                self.fail("Publisher didn't receive enough")
        self.assertTrue(self.pub.lines.empty(), "Too many published lines")

    @unittest.skipUnless(has_ssl, "requires ssl library")
    def test_ssl(self):
        sent_line = "#chan1:Hello, world, from SSL"
        # Start listener
        with kaoz.listener.TCPListener(self.pub, self.ssl_config):
            # Send one line
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock = ssl.wrap_socket(sock)
            sock.connect((self.host, self.port))
            packet = "%s:%s" % (self.password, sent_line)
            sock.sendall(packet.encode('UTF-8'))
            sock.close()

            # Close everything and wait for the publisher to receive the line
            try:
                received_line = self.pub.lines.get(timeout=2)
            except queue.Empty:
                self.fail("Publisher didn't receive anything")
        self.assertEqual(received_line, sent_line)
        self.assertTrue(self.pub.lines.empty(), "Too many published lines")

    def test_commands(self):
        testing_channel = "#testing-channel"
        self.pub.channels([testing_channel])
        with kaoz.listener.TCPListener(self.pub, self.config):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))

            # Get list of channels
            packet = "%s::channels" % (self.password)
            sock.sendall(packet.encode('UTF-8'))
            sock.shutdown(socket.SHUT_WR)
            sock.settimeout(2)
            line = sock.makefile().readline()
            sock.settimeout(None)
            sock.close()
        self.assertEqual(line, testing_channel + "\n")
