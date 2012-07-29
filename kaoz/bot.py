#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright © 2011-2012 Binet Réseau
# See the LICENCE file for more informations

#This file is a part of Kaoz, a free irc notifier

import ConfigParser
import optparse
import sys

from twisted.internet.protocol import ServerFactory, ReconnectingClientFactory
from twisted.application.internet import TCPServer, SSLServer, TCPClient, SSLClient
from twisted.application.service import Application
from twisted.internet.ssl import ClientContextFactory, DefaultOpenSSLContextFactory

import kaoz
from kaoz import publishbot

DEFAULT_CONFIG_FILE = '/etc/kaoz.conf'


class ListenerFactory(ServerFactory):
    def __init__(self, config, *args, **kwargs):
        self.config = config
        super(ListenerFactory, self).__init__(*args, **kwargs)

    def buildProtocol(self, addr):
        return publishbot.Listener(self.config)


class PublisherFactory(ReconnectingClientFactory):
    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.queue = []
        self.connection = None
        super(PublisherFactory, self).__init__(*args, **kwargs)

    def buildProtocol(self, addr):
        return publishbot.Publisher(self.config)


def main(*config_file_paths):
    config = ConfigParser.SafeConfigParser()
    config.read(*config_file_paths)

    application = Application("Kaoz Irc-Notifier")
    server_factory = ListenerFactory(config)
    client_factory = PublisherFactory(config)

    if config.get('listener', 'ssl'):
        server = SSLServer(
            config.get('listener', 'port'),
            server_factory,
            DefaultOpenSSLContextFactory(config.get('listener', 'ssl_cert')),
        )
    else:
        server = TCPServer(config.get('listener', 'port'), server_factory)

    server.setServiceParent(application)

    if config.get('irc', 'ssl'):
        ircservice = SSLClient(
            config.get('irc', 'server'),
            config.get('irc', 'port'),
            client_factory,
            ClientContextFactory(),
        )
    else:
        ircservice = TCPClient(
            config.get('irc', 'server'),
            config.get('irc', 'port'),
            client_factory,
        )

    ircservice.setServiceParent(application)


def get_config_path(argv):
    """Find the file to the right config file."""
    parser = optparse.OptionParser(
        usage="usage: %prog [options]",
        version="%prog " + kaoz.__version__)
    parser.add_option('-c', '--config', action='store', dest='config',
        help=u"Read configuration from CONFIG", metavar="CONFIG",
        default=DEFAULT_CONFIG_FILE)

    opts, argv = parser.parse_args(argv)
    return opts.config


if __name__ == '__main__':
    config_file = get_config_path(sys.argv)
    main(config_file)
