# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

from .common import unittest, get_local_conf, spawn_ircserver
from .common import configure_ircserver_log, configure_logger
import kaoz.publishbot

configure_ircserver_log('INFO')
configure_logger(kaoz.publishbot.logger, 'DEBUG')

# Uncomment to get logging information from irc.client
#import irc.client
#configure_logger(irc.client.log, 'DEBUG')


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
            for num_processings in range(20):
                if pub.is_connected():
                    break
                pub.ircobj.process_once(1)
            self.assertTrue(pub.is_connected(), "connect times out")
        finally:
            pub.stop()

    def test_alreadyinuse_nick(self):
        self.config.set('irc', 'nickname', 'Nick-already-in-use')
        pub = kaoz.publishbot.Publisher(self.config)
        try:
            pub.connect()
            # Process messages until connection is stopped
            for num_processings in range(5):
                if pub.is_stopped():
                    break
                pub.ircobj.process_once(1)
            self.assertTrue(pub.is_stopped(), "connect was not stopped")
        finally:
            pub.stop()

    def test_messages(self):
        # Use Publishbot thread here
        with kaoz.publishbot.PublisherThread(self.config) as pub:
            text = "Hello, world !"
            pub.send('#chan1', text)
            message = self.ircsrv.get_displayed_message(10)
            self.assertFalse(message is None, "unable to display a message")
            self.assertEqual(message.channel, '#chan1')
            self.assertEqual(message.text, text)

            # Send a line
            pub.send_line("#chan1:Message on a line: it works")
            message = self.ircsrv.get_displayed_message(10)
            self.assertFalse(message is None, "unable to display a message")
            self.assertEqual(message.channel, '#chan1')
            self.assertEqual(message.text, "Message on a line: it works")

            # Define a function to have unicode strings in python2 and 3
            import sys

            def u(s):
                if sys.version_info < (3,):
                    return unicode(s, "unicode_escape")
                else:
                    return s

            # Send messages with e acute in UTF-8 and ISO-8859-1
            text = u("e acute may be \xc3\xa9 or \xe9.")
            pub.send_line(u('#ch\xe0n1:') + text)
            message = self.ircsrv.get_displayed_message(10)
            self.assertFalse(message is None, "unable to display a message")
            self.assertEqual(message.channel, u('#ch\xe0n1'))
            self.assertEqual(message.text, text)

    def test_unjoinable_chan(self):
        private_message = "Message for a chan the bot can't join"
        public_message = "Message for a chan where the bot is allowed"
        with kaoz.publishbot.PublisherThread(self.config) as pub:
            pub.send('#unjoinable-chan', private_message)
            pub.send('#public-chan', public_message)
            # The two messages must be seen
            message = self.ircsrv.get_displayed_message(10)
            message2 = self.ircsrv.get_displayed_message(10)
            self.assertFalse(message is None, "unable to display a message")
            self.assertNotEqual(message.channel, '#unjoinable-chan',
                                "unjoinable channel got joinned")
            self.assertNotEqual(message.text, private_message,
                                "private message got published")
            self.assertEqual(message.channel, '#public-chan')
            self.assertEqual(message.text, public_message)
            self.assertEqual(message2.channel, '#fallback')
            self.assertEqual(message2.text, private_message)

            # Check the list of channels
            self.assertItemsEqual(pub.channels(), ['#public-chan', '#fallback'])

    def test_long_message(self):
        bytes_message = b"Long message: " + (b"\xc3\xa9" * 1000)
        long_message = bytes_message.decode('utf-8')
        line_maxlen = kaoz.publishbot.IRC_CHANMSG_MAXLEN - len('#chan')
        with kaoz.publishbot.PublisherThread(self.config) as pub:
            pub.send('#chan', long_message)
            bytes_got = b''
            while len(bytes_got) < len(bytes_message):
                message = self.ircsrv.get_displayed_message(10)
                self.assertFalse(message is None, "message timeout")
                self.assertEqual(message.channel, '#chan', "wrong channel")
                msg_bytes = message.text.encode('utf-8')
                self.assertTrue(len(msg_bytes) <= line_maxlen,
                                "too big message")
                bytes_got += msg_bytes
            self.assertEqual(len(bytes_got), len(bytes_message),
                             "mismatched length")
            self.assertEqual(bytes_got, bytes_message, "corrupted message")
