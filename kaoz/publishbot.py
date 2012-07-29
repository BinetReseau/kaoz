#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright © 2011-2012 Binet Réseau
# See the LICENCE file for more informations

#This file is a part of Kaoz, a free irc notifier

from twisted.words.protocols.irc import IRCClient
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor

from kaoz import config

class Publisher(IRCClient):
    nickname = config.NICK
    password = config.IRC_SERVER_PASSWORD
    realname = config.REAL_NAME
    username = config.USER_NAME
    erroneousNickFallback = config.NICK + '_'
    lineRate = 1
    chans = set() 

    def connectionMade(self):
        print "connection made to!", self.transport
        self.factory.connection = self
        IRCClient.connectionMade(self)
        if self.factory.queued:
            for channel, message in self.factory.queued:
                self.send(channel, message)
        self.factory.queued = []

    def send(self, channel, message):
        if channel not in self.chans:
            self.join(channel)
        self.say(channel, message)
    
    def privmsg(self, user, channel, message):
        if channel == self.nickname:
            self.notice(user.split('!')[0], "I'm a bot, hence I will never answer")

    def kickedFrom(self, channel, kicker, message):
        self.notice(kicker, "That was mean, I'm just a bot you know");
    	reactor.callLater(10, self.join, channel)
        self.chans.remove(channel);

    def nickChanged(self, nick):
        self.nickChanged(self, nick)
        reactor.callLater(10, self.setNick, config.NICK)
        reactor.callLater(300, self.setNick, config.NICK)

    def irc_ERR_NICKNAMEINUSE(self, prefix, params):
        reactor.callLater(3000, self.setNick, config.NICK)

    def joined(self, channel):
        IRCClient.joined(self, channel)
        self.chans.add(channel);

    def left(self, channel):
        IRCClient.left(self, channel)
        self.chans.remove(channel);



class Listener(LineReceiver):
    def __init__(self):
        self.delimiter='\n'

    def connectionMade(self):
        print "Connection made:", self.transport

    def lineReceived(self, line):
        print "Printing message: ", line
        password, channel, message = line.split(':', 2)
        assert password == config.LISTENER_PASSWORD
        if self.factory.publisher.connection:
            print "Sending message:", channel, message
            self.factory.publisher.connection.send(channel, message)
        else:
            print "Queueing message:", channel, message
            self.factory.publisher.queued.append((channel, message))
