#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

"""Core of the Kaoz system."""

import logging
import logging.handlers
import optparse
import os
import sys
import threading

import kaoz
from kaoz import publishbot
from kaoz import listener

if sys.version_info < (3,):
    from ConfigParser import SafeConfigParser as ConfigParser
else:
    from configparser import ConfigParser


logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILE = '/etc/kaoz.conf'


def get_default_config():
    """Build a ConfigParser object with the default configuration"""
    # Do not use the defaults argument of ConfigParser as it applies to all
    # sections
    config = ConfigParser()
    config.add_section('irc')
    config.set('irc', 'server_password', '')
    config.set('irc', 'ssl', 'false')
    config.set('irc', 'reconnection_interval', '60')
    config.set('irc', 'line_sleep', '1')
    config.set('irc', 'fallback_channel', '')
    config.set('irc', 'max_join_attempts', '10')
    config.set('irc', 'memory_timeout', '3600')
    config.set('irc', 'channel_maxlen', '100')
    config.add_section('listener')
    config.set('listener', 'host', '')
    config.set('listener', 'ssl', 'false')
    config.set('listener', 'ssl_cert', '')
    config.add_section('automessages')
    return config


def main(argv):
    """Start bot threads"""
    # Parse command line
    parser = optparse.OptionParser(
        usage="usage: %prog [options]",
        version="%prog " + kaoz.__version__)
    parser.add_option(
        '-c', '--config', action='store', dest='config', metavar="CONFIG",
        help="read configuration from CONFIG",
        default=DEFAULT_CONFIG_FILE)
    parser.add_option(
        '-d', '--debug', action='store_true', dest='debug', default=False,
        help="log debug messages")
    parser.add_option(
        '-l', '--logstd', action='store_true', dest='logstd', default=False,
        help="log messages to standard channel")

    opts, argv = parser.parse_args(argv)

    # Setup logging
    loglevel = logging.DEBUG if opts.debug else logging.INFO
    if opts.logstd:
        logging.basicConfig(level=loglevel)
    else:
        log_handler = logging.handlers.SysLogHandler(
            '/dev/log',
            facility=logging.handlers.SysLogHandler.LOG_DAEMON)
        log_handler.setFormatter(logging.Formatter(
            ('kaoz[%d]: ' % os.getpid()) +
            '[%(levelname)s] %(name)s: %(message)s'))
        root_logger = logging.getLogger()
        root_logger.setLevel(loglevel)
        root_logger.addHandler(log_handler)

    # Read configuration
    config = get_default_config()
    config.read(opts.config)

    # Test wether the configuration gives a good server
    if config.get('irc', 'server').endswith('example.org'):
        logger.fatal(
            "configuration file contains example irc server, aborting")
        sys.exit(1)

    # Start publisher and listener as daemon threads
    event = threading.Event()
    publisher = publishbot.PublisherThread(config, event=event,
                                           debug=opts.debug)
    publisher.daemon = True
    tcplistener = listener.TCPListener(publisher, config, event=event)
    tcplistener.daemon = True
    publisher.start()
    tcplistener.start()

    # Wait everybody to end, which means error
    event.wait()
    sys.exit(1)
