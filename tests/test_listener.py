# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

from .common import unittest, get_local_conf
import kaoz.listener
import Queue
import socket


class DummyPublisher(object):
    """Publisher for testing purpose"""

    def __init__(self):
        self.lines = Queue.Queue()

    def send_line(self, line):
        """Listener sends a line to the publisher"""
        self.lines.put(line)


class ListenerTestCase(unittest.TestCase):

    def setUp(self):
        self.config = get_local_conf()
        self.host = self.config.get('listener', 'host')
        self.port = self.config.getint('listener', 'port')
        self.password = self.config.get('listener', 'password')
        self.pub = DummyPublisher()

    def tearDown(self):
        del self.pub

    def test_listener(self):
        sent_line = u"%s:#chan1:Hello, world" % self.password
        # Start listener
        with kaoz.listener.TCPListener(self.pub, self.config):
            # Send one line
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            sock.sendall(sent_line)
            sock.close()
        # Close everything and wait for the publisher to receive the line
        try:
            received_line = self.pub.lines.get(timeout=1)
        except Queue.Empty:
            self.fail(u"Publisher didn't receive anything")
        self.assertEquals(received_line, sent_line)
        self.assertTrue(self.pub.lines.empty(), u"Too many published lines")

    def test_multiple_lines(self):
        sent_lines = map(
            lambda i: u"%s:#chan%d:Line %d" % (self.password, i, i),
            range(10))
        with kaoz.listener.TCPListener(self.pub, self.config):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            sock.sendall(u"\r\n".join(sent_lines))
            sock.close()
        try:
            for l in sent_lines:
                received_line = self.pub.lines.get(timeout=1)
                self.assertEquals(received_line, l, u"Wrong published line")
        except Queue.Empty:
            self.fail(u"Publisher didn't receive enough")
        self.assertTrue(self.pub.lines.empty(), u"Too many published lines")
