# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

# This file is a part of Kaoz, a free irc notifier

import irc.client
import irc.connection
import logging
import sys
import threading
import traceback

import kaoz.channel

if sys.version_info < (3,):
    import Queue as queue
else:
    import queue

try:
    import ssl
    has_ssl = True
except ImportError:
    has_ssl = False

logger = logging.getLogger(__name__)


# IRC limit on message and channel name length.
# According to the RFC http://tools.ietf.org/html/rfc2812#page-6, a message is
# admissible only if the IRC client won't eventually have to send a message
# longer than 512 bytes.
# The message that will be sent by the irc.client module is:
#     'PRIVMSG {channel} :{message}\r\n'
# so we only send messages which satisfy:
#     len(channel) + len(message) <= 512 - 12
IRC_CHANMSG_MAXLEN = 500


def utf8_cut(bytestr, maxlen):
    """Cuts an utf8 bytestring in two parts where the left is at most maxlen
    long, and both are valid utf8 strings.
    """
    left = bytestr[:maxlen].decode('utf-8', 'ignore').encode('utf-8')
    return left, bytestr[len(left):]


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
        self._fallbackchan = config.get('irc', 'fallback_channel')
        self._max_join_attempts = config.getint('irc', 'max_join_attempts')
        self._memory_timeout = config.getint('irc', 'memory_timeout')
        self._channel_maxlen = config.getint('irc', 'channel_maxlen')

        if self._channel_maxlen < 1 or \
            self._channel_maxlen > IRC_CHANMSG_MAXLEN - 1:
            logger.warning("Invalid channel_maxlen value (%d), using 100" %
                           self._channel_maxlen)
            self._channel_maxlen = 100

        self._chans = kaoz.channel.IndexedChanDict()
        self._queue = queue.Queue()
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
            logger.info("connecting to %s:%d..." % (self._server, self._port))
            if self._use_ssl:
                assert has_ssl, "SSL support requested but not available"
                conn_factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
            else:
                conn_factory = irc.connection.Factory()
            try:
                super(Publisher, self).connect(
                    self._server, self._port, self._nickname,
                    password=self._password,
                    username=self._username,
                    ircname=self._realname,
                    connect_factory=conn_factory)
                # Don't raise UnicodeDecodeError exception
                # when the server doesn't speak UTF-8
                self.connection.buffer.errors = 'replace'

                # Configure keep-alive pings, if available
                if hasattr(self.connection, 'set_keepalive'):
                    self.connection.set_keepalive(60)
            except irc.client.ServerConnectionError as e:
                logger.error("Error connecting to %s: %s" % (self._server, e))

    def _check_connect(self):
        """Force reconnection periodically"""
        if (not self.is_connected()) and (not self._stop.is_set()):
            self.connect()

    def on_nicknameinuse(self, connection, event):
        """Nickname is already in use

        This is a fatal error as this means something in the configuration
        went wrong.
        """
        logger.fatal("Nickname %s is already in use. Abort!" % self._nickname)
        self.stop()

    def on_welcome(self, connection, event):
        """Handler for post-connection event.

        Send all queued messages.
        """
        logger.info("connection made to %s" % event.source)
        self._has_welcome = True

    def on_disconnect(self, connection, event):
        """On disconnect, reconnect !"""
        logger.info("disconnect event received")
        self._chans.leave_all()
        self._has_welcome = False

    def on_join(self, connection, event):
        """Join a new channel, say what we need"""
        # Check message is for me
        nick = event.source.nick
        if nick != connection.get_nickname():
            return
        channel = event.target
        logger.info("Joined channel %s" % channel)
        self._chans[channel].mark_joined()

    def on_kick(self, connection, event):
        """Kicked from a channel"""
        if len(event.arguments) < 1:
            return
        nick = event.arguments[0]
        if nick != connection.get_nickname():
            return
        channel = event.target
        kicker = event.source
        logger.info("kicked from channel %s by %s" % (channel, kicker))
        self.connection.notice(kicker,
                               "That was mean, I'm just a bot you know")
        self._chans.leave(channel)

    def on_part(self, connection, event):
        """Parted from a channel"""
        nick = event.source.nick
        if nick != connection.get_nickname():
            return
        channel = event.target
        logger.info("parted from channel %s" % channel)
        self._chans.leave(channel)

    def on_invite(self, connection, event):
        nick = event.target
        if nick != connection.get_nickname() or len(event.arguments) < 1:
            return
        channel = event.arguments[0]
        logger.info("invited to channel %s" % channel)
        self.send(channel, "I'm been invited here.")

    def on_privmsg(self, connection, event):
        """Answer to a user privmsg and die on demand"""
        self.connection.privmsg(event.source.nick,
                                "I'm a bot, hence I will never answer")

    def send(self, channel, message):
        """Send a message to a channel. Join the channel before talking.

        This is the interface of this class and is thread-safe.

        channel and message are unicode strings.
        """
        if len(channel.encode('utf8')) > self._channel_maxlen:
            logger.warning("Channel length limit exceeded, dropping message")
            return
        self._queue.put((channel, message))

    def _say_messages(self):
        """Try to send as much waiting messages as possible.

        This function is called every "line_sleep" seconds and only do one task
        such as publishing a line, joining a chan or something else.
        """
        # Dequeue everything, creating channel objects if needed
        while not self._queue.empty():
            (channel, message) = self._queue.get()
            # Split message if it is too long
            channel_length = len(channel.encode('utf8'))
            max_message_size = IRC_CHANMSG_MAXLEN - channel_length
            # Need at least 5 characters
            if max_message_size <= 5:
                logger.error("Channel name too long, dropping message")
                continue
            encoded = message.encode('utf-8')
            while len(encoded) > max_message_size:
                left, encoded = utf8_cut(encoded, max_message_size)
                if not left:
                    logger.error("Unable to decode message, dropping it")
                    break
                self._chans[channel].messages.append(left.decode('utf-8'))
            if encoded and len(encoded) <= max_message_size:
                self._chans[channel].messages.append(
                    encoded.decode('utf-8', 'ignore'))

        # Don't do anything if server is stopped
        if self._stop.is_set():
            return

        # If we're disconnected, don't do anything and wait for reconnection
        if not self.is_connected():
            return

        # Find the next channel which needs work
        chanstatus = self._chans.find_waiting_channel()
        if chanstatus is None:
            return

        # Join the channel if needed
        if chanstatus.need_join():
            if chanstatus.inc_join_counter(self._max_join_attempts,
                                           self._memory_timeout):
                self.connection.join(chanstatus.name)
            elif self._fallbackchan and chanstatus.name != self._fallbackchan:
                # Channel is blocked. Do fallback !
                logger.warning("Channel %s is blocked. Using fallback" %
                               chanstatus.name)
                message = chanstatus.messages.pop(0)
                self._chans[self._fallbackchan].messages.append(message)
            else:
                logger.error("Channel %s is blocked. Dropping message" %
                             chanstatus.name)
                message = chanstatus.messages.pop(0)
                logger.error("Dropped message was %s" % message)
            return

        # Say first message and unqueue
        message = chanstatus.messages.pop(0)
        logger.info("[%s] say %s" % (chanstatus.name, message))
        self.connection.privmsg(chanstatus.name, message)

    def is_connected(self):
        """Tell wether the bot is connected or not"""
        return self.connection.is_connected() and self._has_welcome

    def is_stopped(self):
        """Tell wether the connection is stopped"""
        return self._stop.is_set()

    def run(self):
        """Infinite loop of message processing"""
        # There is a periodic task which checks connection
        # but don't wait for it to start connection
        if not self.is_connected():
            self.connect()
        while not self._stop.is_set():
            # Start infinite loop
            try:
                self.ircobj.process_once(0.2)
            except:
                logger.critical("An exception occured in IRC bot:")
                for line in traceback.format_exc().splitlines():
                    logger.critical(".. " + line)

    def stop(self):
        """Stop IRC client"""
        self._stop.set()
        if self.is_connected():
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
                logger.critical("Exception " + traceback.format_exc())
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
