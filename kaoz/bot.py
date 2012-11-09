#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright © 2011-2012 Binet Réseau
# See the LICENCE file for more informations

"""Core of the Kaoz system."""

import ConfigParser
import logging
import logging.handlers
import optparse

import kaoz
from kaoz import publishbot
from kaoz import listener


DEFAULT_CONFIG_FILE = '/etc/kaoz.conf'

DEFAULT_CONFIG = {
    'server_password': '',
    'ssl': 'false',
    'ssl_cert': '',
    'reconnection_interval': '60',
    'host': '',
}


def main(*config_file_paths):
    # Setup logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(logging.handlers.SysLogHandler('/dev/log'))

    # Read configuration
    config = ConfigParser.SafeConfigParser(DEFAULT_CONFIG)
    config.read(*config_file_paths)

    # Start publisher and listener
    publisher = publishbot.PublisherThread(config)
    tcplistener = listener.TCPListener(publisher, config)
    publisher.start()
    tcplistener.start()

    # Wait everybody to end
    tcplistener.join()
    publisher.join()


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
