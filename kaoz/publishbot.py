# -*- coding: utf-8 -*-
# Copyright © 2011-2012 Binet Réseau
# See the LICENCE file for more informations

#This file is a part of Kaoz, a free irc notifier

import logging

from twisted.words.protocols.irc import IRCClient
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor

logger = logging.getLogger(__name__)


class Publisher(IRCClient):
    def __init__(self, config, *args, **kwargs):
        """Instantiate the publisher based on configuration."""
        self.nickname = config.get('irc', 'nickname')
        self.realname = config.get('irc', 'realname')
        self.username = config.get('irc', 'username')
        self.password = config.get('irc', 'server_password')

        erroneousNickFallback = self.nickname + '_'
        self.lineRate = 1
        self.chans = set()
        super(Publisher, self).__init__(*args, **kwargs)

    def connectionMade(self):
        """Handler for post-connection event.

        Send all queued messages.
        """
        logger.info(u"connection made to %s", self.transport)
        self.factory.connection = self
        super(Publisher, self).connectionMade()

        if self.factory.queued:
            for channel, message in self.factory.queued:
                self.send(channel, message)
        self.factory.queued = []

    def send(self, channel, message):
        """Send a message to a channel. Will join the channel before talking."""
        if channel not in self.chans:
            self.join(channel)
        self.say(channel, message)
    
    def privmsg(self, user, channel, message):
        """Answer to a user privmsg."""
        if channel == self.nickname:
            self.notice(user.split('!')[0], "I'm a bot, hence I will never answer")

    def kickedFrom(self, channel, kicker, message):
        """Handler for kicks. Will join the channel back after 10 seconds."""
        self.notice(kicker, "That was mean, I'm just a bot you know");
    	reactor.callLater(10, self.join, channel)
        self.chans.remove(channel);
        super(Publisher, self).kickedFrom(channel, kicker, message)

    def nickChanged(self, nick):
        """Will try to return to initial nick after 10 and 300 seconds."""
        super(Publisher, self).nickChanged(nick)
        reactor.callLater(10, self.setNick, self.nickname)
        reactor.callLater(300, self.setNick, self.nickname)

    def irc_ERR_NICKNAMEINUSE(self, prefix, params):
        """If the chosen nickname is currently in use."""
        reactor.callLater(3000, self.setNick, self.nickname)

    def joined(self, channel):
        """Upon joining a channel"""
        super(Publisher, self).joined(channel)
        self.chans.add(channel);

    def left(self, channel):
        """Upon leaving a channel"""
        super(Publisher, self).left(channel)


class Listener(LineReceiver):
    def __init__(self, config):
        self.delimiter='\n'
        self.expected_password = config.get('listener', 'password')

    def connectionMade(self):
        """When a client connects"""
        logger.info(u"Connection made: %s", self.transport)

    def lineReceived(self, line):
        """When a line is received."""
        logger.info(u"Printing message: %s", line)
        password, channel, message = line.split(':', 2)
        if password != self.expected_password:
            logger.error(u"Invalid password %s on line %s", password, line)
            return

        if self.factory.publisher.connection:
            logger.info(u"Sending message to %s: %s", channel, message)
            self.factory.publisher.connection.send(channel, message)
        else:
            logger.info(u"Queuing message to %s: %s", channel, message)
            self.factory.publisher.queued.append((channel, message))
