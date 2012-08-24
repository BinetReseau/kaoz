#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright © 2011-2012 Binet Réseau
# See the LICENCE file for more informations

"""Core of the Kaoz system."""

import ConfigParser
import collections
import optparse

from twisted.application import app as twisted_app
from twisted.application.internet import TCPServer, TCPClient

try:
    from twisted.application.internet import SSLClient, SSLServer
    from twisted.internet.ssl import ClientContextFactory, DefaultOpenSSLContextFactory
    has_ssl = True
except ImportError:
    SSLClient = SSLServer = None
    ClientContextFactory = DefaultOpenSSLContextFactory = None
    has_ssl = False

from twisted.application.service import Application, IService
from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory, ReconnectingClientFactory

import kaoz
from kaoz import publishbot

DEFAULT_CONFIG_FILE = '/etc/kaoz.conf'


class ListenerFactory(ServerFactory):
    """Kaoz server.

    Attributes:
        config (dict): current configuration.
    """

    def __init__(self, config, publisher, *args, **kwargs):
        self.config = config
        self.publisher = publisher
        # Twisted still uses old-style classes, 10 years later. Sigh.
        # And the parent has no __init__, yay.

    def buildProtocol(self, addr):
        protocol = publishbot.Listener(self.config)
        protocol.factory = self
        return protocol


class PublisherFactory(ReconnectingClientFactory):
    """IRC publisher client.

    Attributes:
        config (dict): current configuration
        queue (list): messages to send
    """

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.queue = collections.deque()
        self.connection = None
        # Twisted still uses old-style classes, 10 years later. Sigh.
        # And the parent has no __init__, yay.

    def buildProtocol(self, addr):
        protocol = publishbot.Publisher(self.config)
        protocol.factory = self
        return protocol


def make_application(*config_file_paths):
    """Parse configuration and launch a kaoz client/server process.

    Args:
        config_file_paths: list of paths to search for configuration files.

    Returns:
        A twisted Application object
    """
    config = ConfigParser.SafeConfigParser()
    config.read(*config_file_paths)

    application = Application("Kaoz Irc-Notifier")
    client_factory = PublisherFactory(config)
    server_factory = ListenerFactory(config, client_factory)

    listen_port = int(config.get('listener', 'port'))

    if config.get('listener', 'ssl', 'false') == 'true':
        assert has_ssl, "SSL support requested but not available"
        ssl_context = DefaultOpenSSLContextFactory(
            config.get('listener', 'ssl_cert'),  # The key
            config.get('listener', 'ssl_cert'),  # The certificate
        )
        server = SSLServer(listen_port, server_factory, ssl_context)
    else:
        server = TCPServer(listen_port, server_factory)

    server.setServiceParent(application)

    # IRC
    irc_server = config.get('irc', 'server')
    irc_port = int(config.get('irc', 'port'))

    if config.get('irc', 'ssl', 'false') == 'true':
        assert has_ssl, "SSL support requested but not available"
        ssl_context = ClientContextFactory()
        ircservice = SSLClient(irc_server, irc_port, client_factory, ssl_context)
    else:
        ircservice = TCPClient(irc_server, irc_port, client_factory)

    ircservice.setServiceParent(application)

    return application

def main(*config_file_paths):
    import logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(logging.StreamHandler())
    root_logger.debug("COIN")
    application = make_application(*config_file_paths)
    service = IService(application)
    service.startService()
    reactor.addSystemEventTrigger('before', 'shutdown', service.stopService)
    reactor.run()


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
