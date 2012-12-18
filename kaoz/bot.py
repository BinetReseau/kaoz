#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright © 2011-2012 Binet Réseau
# See the LICENCE file for more informations

"""Core of the Kaoz system."""

import ConfigParser
import logging
import logging.handlers
import optparse
import os
import sys
import threading

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
    'line_sleep': '1',
}


def main(argv):
    """Start bot threads"""
    # Parse command line
    parser = optparse.OptionParser(
        usage="usage: %prog [options]",
        version="%prog " + kaoz.__version__)
    parser.add_option('-c', '--config', action='store', dest='config',
        help=u"Read configuration from CONFIG", metavar="CONFIG",
        default=DEFAULT_CONFIG_FILE)
    parser.add_option('-l', '--logstd', action='store_true', dest='logstd',
        help="Log messages to standard channel", default=False)

    opts, argv = parser.parse_args(argv)

    # Setup logging
    if opts.logstd:
        logging.basicConfig(level=logging.INFO)
    else:
        log_handler = logging.handlers.SysLogHandler('/dev/log',
            facility=logging.handlers.SysLogHandler.LOG_DAEMON)
        log_handler.setFormatter(logging.Formatter(('kaoz[%d]: ' % os.getpid())
            + '[%(levelname)s] %(name)s: %(message)s'))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(log_handler)

    # Read configuration
    config = ConfigParser.SafeConfigParser(DEFAULT_CONFIG)
    config.read(opts.config)

    # Start publisher and listener as daemon threads
    event = threading.Event()
    publisher = publishbot.PublisherThread(config, event=event)
    publisher.daemon = True
    tcplistener = listener.TCPListener(publisher, config, event=event)
    tcplistener.daemon = True
    publisher.start()
    tcplistener.start()

    # Wait everybody to end, which means error
    event.wait()
    sys.exit(1)
