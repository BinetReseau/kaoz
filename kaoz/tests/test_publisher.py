# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

from .common import unittest, get_local_conf, spawn_ircserver
from .common import configure_ircserver_log, configure_logger
import kaoz.publishbot

configure_ircserver_log('INFO')
configure_logger(kaoz.publishbot.logger, 'DEBUG')


class PublisherTestCase(unittest.TestCase):

    def setUp(self):
        self.config = get_local_conf()
        self.ircsrv = spawn_ircserver(self.config)

    def tearDown(self):
        self.ircsrv.stop()
        del self.ircsrv

    def test_welcome(self):
        pub = kaoz.publishbot.Publisher(self.config)
        try:
            pub.connect()
            # Process messages until welcome comes
            # Count how many messages are processed to avoid a blocking test
            num_messages = 0
            while not pub.is_connected() and num_messages < 20:
                pub.ircobj.process_once(1)
                num_messages = num_messages + 1
            self.assertTrue(pub.is_connected(), u"connect times out")
        finally:
            pub.stop()

    def test_messages(self):
        # Use Publishbot thread here
        with kaoz.publishbot.PublisherThread(self.config) as pub:
            # Send messages
            pub.send('#chan1', u"Hello, world !")
            message = self.ircsrv.get_displayed_message(10)
            self.assertFalse(message is None, u"unable to display a message")
            self.assertTrue(message.channel == '#chan1')
            self.assertTrue(message.text == u"Hello, world !")

            # Send a line
            pub.send_line(u"#chan1:Message on a line: it works")
            message = self.ircsrv.get_displayed_message(10)
            self.assertFalse(message is None, u"unable to display a message")
            self.assertTrue(message.channel == '#chan1')
            self.assertTrue(message.text == u"Message on a line: it works")

    def test_unjoinable_chan(self):
        private_message = u"Message for a chan the bot can't join"
        public_message = u"Message for a chan where the bot is allowed"
        with kaoz.publishbot.PublisherThread(self.config) as pub:
            pub.send('#unjoinable-chan', private_message)
            pub.send('#public-chan', public_message)
            message = self.ircsrv.get_displayed_message(10)
            self.assertFalse(message is None, u"unable to display a message")
            self.assertTrue(message.channel != '#unjoinable-chan',
                            u"unjoinable channel got joinned")
            self.assertTrue(message.text != private_message,
                            u"private message got published")
            self.assertTrue(message.channel == '#public-chan')
            self.assertTrue(message.text == public_message)
