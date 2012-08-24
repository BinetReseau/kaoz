#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright © 2011-2012 Binet Réseau
# See the LICENCE file for more informations

"""Core of the Kaoz system."""

import ConfigParser
import optparse

from twisted.internet.protocol import ServerFactory, ReconnectingClientFactory
from twisted.application.internet import TCPServer, SSLServer, TCPClient, SSLClient
from twisted.application.service import Application
from twisted.internet.ssl import ClientContextFactory, DefaultOpenSSLContextFactory

import kaoz
from kaoz import publishbot

DEFAULT_CONFIG_FILE = '/etc/kaoz.conf'


class ListenerFactory(ServerFactory):
    """Kaoz server.

    Attributes:
        config (dict): current configuration.
    """

    def __init__(self, config, *args, **kwargs):
        self.config = config
        super(ListenerFactory, self).__init__(*args, **kwargs)

    def buildProtocol(self, addr):
        return publishbot.Listener(self.config)


class PublisherFactory(ReconnectingClientFactory):
    """IRC publisher client.

    Attributes:
        config (dict): current configuration
        queue (list): messages to send
    """

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.queue = []
        self.connection = None
        super(PublisherFactory, self).__init__(*args, **kwargs)

    def buildProtocol(self, addr):
        return publishbot.Publisher(self.config)


def main(*config_file_paths):
    """Parse configuration and launch a kaoz client/server process.

    Args:
        config_file_paths: list of paths to search for configuration files.
    """
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
