# -*- coding: utf-8 -*-
# Copyright © 2011-2012 Binet Réseau
# See the LICENCE file for more informations

# This file is a part of Kaoz, a free irc notifier

import irc.client
import irc.connection
import logging
import Queue
import threading
import traceback

try:
    import ssl
    has_ssl = True
except ImportError:
    has_ssl = False

logger = logging.getLogger(__name__)


class Publisher(irc.client.SimpleIRCClient):
    """A basic IRC publisher which sends lines to IRC

    This class uses a Queue to get messages from the outside. It deques the
    messages into an internal list which containes (channel, message) tuples,
    waiting to be sent. When the bot joined a channel, it may send waiting
    messages out, in a relatively slow rate to prevent server spamming.
    """

    def __init__(self, config, *args, **kwargs):
        """Instantiate the publisher based on configuration."""
        super(Publisher, self).__init__()
        self._server = config.get('irc', 'server')
        self._port = config.getint('irc', 'port')
        self._use_ssl = config.getboolean('irc', 'ssl')
        self._reconn_interval = config.getint('irc', 'reconnection_interval')
        self._nickname = config.get('irc', 'nickname')
        self._realname = config.get('irc', 'realname')
        self._username = config.get('irc', 'username')
        self._password = config.get('irc', 'server_password')
        self._line_sleep = config.getint('irc', 'line_sleep')
        self._chans = set()
        self._queue = Queue.Queue()
        self._messages = list()

    def _connect(self):
        """Connect to a server"""
        try:
            logger.info(u"connecting to %s..." % self._server)
            if self._use_ssl:
                assert has_ssl, "SSL support requested but not available"
                conn_factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
            else:
                conn_factory = irc.connection.Factory()
            self.connect(self._server, self._port, self._nickname,
                         password=self._password,
                         ircname=self._realname,
                         connect_factory=conn_factory)
        except irc.client.ServerConnectionError:
            pass

    def _connected_checker(self):
        """Force reconnection periodically"""
        if not self.connection.is_connected():
            self.connection.execute_delayed(self._reconn_interval,
                                            self._connected_checker)
            self._connect()

    def on_welcome(self, connection, event):
        """Handler for post-connection event.

        Send all queued messages.
        """
        logger.info(u"connection made to %s", event.source)

    def on_disconnect(self, connection, event):
        """On disconnect, reconnect !"""
        self._chans = set()
        self.connection.execute_delayed(self._reconn_interval,
                                        self._connected_checker)

    def on_join(self, connection, event):
        """Join a new channel, say what we need"""
        # Check message is for me
        nick = event.source.nick
        if nick != connection.get_nickname():
            return
        channel = event.target
        logger.info(u"Joined channel %s" % channel)
        self._chans.add(channel)

    def on_kick(self, connection, event):
        """Kicked from a channel"""
        nick = event.arguments[0]
        if nick != connection.get_nickname():
            return
        channel = event.target
        kicker = event.source
        logger.info(u"kicked from channel %s by %s" % (channel, kicker))
        self.connection.notice(kicker,
                               u"That was mean, I'm just a bot you know")
        self._chans.remove(channel)

    def on_part(self, connection, event):
        """Parted from a channel"""
        nick = event.arguments[0]
        if nick != connection.get_nickname():
            return
        channel = event.target
        logger.info("parted from channel %s" % channel)
        self._chans.remove(channel)

    def on_privmsg(self, connection, event):
        """Answer to a user privmsg and die on demand"""
        self.connection.privmsg(event.source.nick,
                                u"I'm a bot, hence I will never answer")

    def send(self, channel, message):
        """Send a message to a channel. Join the channel before talking."""
        self._queue.put((channel, message))

    def _say_messages(self):
        """Try to send as much waiting messages as possible"""
        # Dequeue everything
        while not self._queue.empty():
            (channel, message) = self._queue.get()
            self._messages.append((channel, message))

        # If we're disconnected, don't do anything
        # just wait for reconnection
        if self._messages and self.connection.is_connected():
            (channel, message) = self._messages[0]
            if irc.client.is_channel(channel) and not channel in self._chans:
                # Need to join the channel first
                self.connection.join(channel)
            else:
                # Say and unqueue
                self._messages = self._messages[1:]
                logger.info("[%s] say %s" % (channel, message))
                self.connection.privmsg(channel, message)

        # Infinite loop
        self.connection.execute_delayed(self._line_sleep, self._say_messages)

    def run(self):
        """Infinite loop of message processing
        """
        self._say_messages()
        self._connect()
        import time
        time.sleep(1)
        while True:
            # Start infinite loop, ignoring UnicodeDecodeError
            try:
                self.start()
                return
            except UnicodeDecodeError:
                pass


class PublisherThread(threading.Thread):
    """Thread to manage a Publisher"""

    def __init__(self, config, event=None, debug=False, *args, **kwargs):
        """ Initialise a publisher depending on the configuration and
        optionally set an event when the thread ends.
        """
        self._publisher = Publisher(config, *args, **kwargs)
        super(PublisherThread, self).__init__()
        self._expected_password = config.get('listener', 'password')
        self._event = event
        self._debug = debug

    def run(self):
        try:
            self._publisher.run()
        except:
            if self._debug:
                logger.critical("Exeption " + traceback.format_exc())
            else:
                logger.critical(traceback.format_exc().splitlines()[-1])
        finally:
            if self._event:
                self._event.set()

    def send(self, channel, message):
        self._publisher.send(channel, message)

    def send_line(self, line):
        """Process a line which contains password:channel:message"""
        line_parts = line.split(':', 2)
        if len(line_parts) != 3:
            logger.warning("Invalid message: %s", line)
            return

        password, channel, message = line_parts
        if password != self._expected_password:
            logger.warning(u"Invalid password %s on line %s", password, line)
            return
        self.send(channel, message)
