# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
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


class ChanStatus(object):
    """A simple structure which holds information about a channel

    Note that this structure is not thread-safe. It must only be manipulated
    from Publisher functions.
    """

    def __init__(self, name):
        self.name = name
        self.is_joined = False
        self.join_attemps = 0
        self.messages = list()


class IndexedChanDict(dict):
    """Dictionary of ChanStatus with an index.

    The index is used when saying messages on IRC, to remember the next channel
    to take into account.
    """

    def __init__(self):
        # channel name => ChanStatus mapping
        super(IndexedChanDict, self).__init__()
        # Ordered channel names, to be used when running a loop
        self._list = list()

    def __getitem__(self, channel):
        """Get a ChanStatus or create a new one if it does not exist"""
        if channel not in self:
            self[channel] = ChanStatus(channel)
        return super(IndexedChanDict, self).__getitem__(channel)

    def __setitem__(self, channel, status):
        """Set a specific ChanStatus"""
        if channel not in self:
            self._list.append(channel)
        return super(IndexedChanDict, self).__setitem__(channel, status)

    def __delitem__(self, channel):
        """Delete a channel status"""
        super(IndexedChanDict, self).__delitem__(channel)
        self._list.remove(channel)

    def leave(self, channel):
        """Remove given channel due to a kick or a part"""
        if channel not in self:
            return
        self[channel].is_joined = False
        if not self[channel].messages:
            del self[channel]

    def find_waiting_channel(self):
        """Find a channel which has messages waiting to be sent, or None"""
        for (i, channel) in enumerate(self._list):
            if self[channel].messages:
                self._list = self._list[(i+1):] + self._list[0:i+1]
                return self[channel]
        return None


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
        self._chans = IndexedChanDict()
        self._queue = Queue.Queue()
        self._connect_lock = threading.Lock()
        self._has_welcome = False
        self._stop = threading.Event()
        self.ircobj.execute_every(self._reconn_interval, self._check_connect)
        self.ircobj.execute_every(self._line_sleep, self._say_messages)

    def connect(self):
        """Connect to a server"""
        with self._connect_lock:
            if self._stop.is_set() or self.is_connected():
                # Don't connect if server is stopped or if it is already
                return
            logger.info(u"connecting to %s:%d..." % (self._server, self._port))
            if self._use_ssl:
                assert has_ssl, "SSL support requested but not available"
                conn_factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
            else:
                conn_factory = irc.connection.Factory()
            try:
                super(Publisher, self).connect(self._server, self._port,
                                               self._nickname,
                                               password=self._password,
                                               ircname=self._realname,
                                               connect_factory=conn_factory)
            except irc.client.ServerConnectionError:
                logger.error(u"Error connecting to %s" % self._server)

    def _check_connect(self):
        """Force reconnection periodically"""
        if (not self.is_connected()) and (not self._stop.is_set()):
            self.connect()

    def on_welcome(self, connection, event):
        """Handler for post-connection event.

        Send all queued messages.
        """
        logger.info(u"connection made to %s" % event.source)
        self._has_welcome = True

    def on_disconnect(self, connection, event):
        """On disconnect, reconnect !"""
        logger.info(u"disconnect event received")
        for chan in list(self._chans):
            self._chans.leave(chan)
        self._has_welcome = False

    def on_join(self, connection, event):
        """Join a new channel, say what we need"""
        # Check message is for me
        nick = event.source.nick
        if nick != connection.get_nickname():
            return
        channel = event.target
        logger.info(u"Joined channel %s" % channel)
        self._chans[channel].is_joined = True

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
        if channel in self._chans:
            del self._chans[channel]

    def on_part(self, connection, event):
        """Parted from a channel"""
        nick = event.arguments[0]
        if nick != connection.get_nickname():
            return
        channel = event.target
        logger.info("parted from channel %s" % channel)
        if channel in self._chans:
            del self._chans[channel]

    def on_privmsg(self, connection, event):
        """Answer to a user privmsg and die on demand"""
        self.connection.privmsg(event.source.nick,
                                u"I'm a bot, hence I will never answer")

    def send(self, channel, message):
        """Send a message to a channel. Join the channel before talking.

        This is the interface of this class and is thread-safe
        """
        self._queue.put((channel, message))

    def _say_messages(self):
        """Try to send as much waiting messages as possible.

        This function is called every "line_sleep" seconds and only do one task
        such as publishing a line, joining a chan or something else.
        """
        # Dequeue everything, creating channel objects if needed
        while not self._queue.empty():
            (channel, message) = self._queue.get()
            self._chans[channel].messages.append(message)

        # Don't do anything if server is stopped
        if self._stop.is_set():
            return

        # If we're disconnected, don't do anything and wait for reconnection
        if not self.is_connected():
            return

        # Find the next channel which needs work
        chanstatus = self._chans.find_waiting_channel()
        channel = chanstatus.name

        # Join the channel if needed
        if irc.client.is_channel(channel) and not chanstatus.is_joined:
            self.connection.join(channel)
            chanstatus.join_attemps = chanstatus.join_attemps + 1
            return

        # Say first message and unqueue
        message = chanstatus.messages.pop(0)
        logger.info("[%s] say %s" % (channel, message))
        self.connection.privmsg(channel, message)

    def is_connected(self):
        """Tell wether the bot is connected or not"""
        return self.connection.is_connected() and self._has_welcome

    def run(self):
        """Infinite loop of message processing"""
        # There is a periodic task which checks connection
        # but don't wait for it to start connection
        if not self.is_connected():
            self.connect()
        while not self._stop.is_set():
            # Start infinite loop, ignoring UnicodeDecodeError
            try:
                self.ircobj.process_once(0.2)
            except UnicodeDecodeError:
                pass

    def stop(self):
        """Stop IRC client"""
        self._stop.set()
        self.connection.close()


class PublisherThread(threading.Thread):
    """Thread to manage a Publisher"""

    def __init__(self, config, event=None, debug=False, *args, **kwargs):
        """ Initialise a publisher depending on the configuration and
        optionally set an event when the thread ends.
        """
        self._publisher = Publisher(config, *args, **kwargs)
        super(PublisherThread, self).__init__()
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

    def stop(self):
        """Stop publisher and join it"""
        self._publisher.stop()
        self.join()

    def send(self, channel, message):
        self._publisher.send(channel, message)

    def send_line(self, line):
        """Process a line which contains channel:message"""
        line_parts = line.split(':', 1)
        if len(line_parts) != 2:
            logger.warning("Invalid message: %s", line)
            return

        channel, message = line_parts
        self.send(channel, message)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
