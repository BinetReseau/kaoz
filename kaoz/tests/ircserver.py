#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

"""Basic IRC server, used for testing purpose only

This server specificly does following things:
    * Each user has its own view of channels.
    * There is no right on channel. Everyone is free to do everything.
    * The server shows some users who don't do anything.
    * Users can't interact with each other, but may interact with server bots.
"""

import logging
import optparse
import Queue
import re
import threading
import SocketServer
import sys

logger = logging.getLogger(__name__)

_rfc_1459_command_regexp = re.compile(r'^(:(?P<prefix>[^ ]+) +)?'
    r'(?P<command>[^ ]+)( *(?P<argument> .+))?')

SERVER_VERSION = u"test-ircserver-0.0.1alpha"
SERVER_INFO = u"aAbcCdefFghHiIjkKmnoOrRsvwxXy bceiIjklLmMnoOprRstv"


class _IRCServerHandler(SocketServer.StreamRequestHandler):
    """Manage a request from TCP listener module"""

    def parse_command(self, line):
        """Parse next line sent by the client"""
        m = _rfc_1459_command_regexp.match(line)
        if not m:
            raise IOError(u"Received invalid line: %s" % line)
        args = []
        if m.group('argument'):
            a = m.group('argument').split(u" :", 1)
            args = a[0].split()
            if len(a) == 2:
                args.append(a[1])

        return (m.group('prefix'), m.group('command').upper(), args)

    def dispatch_command(self, line):
        """Dispatch a received line among handlers"""
        (prefix, cmd, args) = self.parse_command(line)
        logger.debug(u"Dispatch (%s, %s, %s)" % (prefix, cmd, args))
        m = "on_" + cmd.lower()
        if hasattr(self, m):
            getattr(self, m)(prefix, args)
        else:
            logger.warning("No handler for command %s" % cmd)

    def on_nick(self, prefix, args):
        """Process received NICK command"""
        assert(len(args) >= 1 and args[0])
        self._nick = args[0]
        if self._username:
            self.do_welcome()

    def on_user(self, prefix, args):
        """Process received USER command"""
        assert(len(args) >= 1 and args[0])
        self._username = args[0]
        if self._nick:
            self.do_welcome()

    def on_join(self, prefix, args):
        """Process received JOIN command"""
        assert(len(args) >= 1 and args[0])
        channel = args[0]
        if not channel in self._chans:
            logger.info(u"Create channel %s with user %s" %
                (channel, self._nick))
            self._chans[channel] = set([self._nick])
        elif not self._nick in self._chans[channel]:
            logger.info(u"User %s joins channel %s" % (self._nick, channel))
            self._chans[channel].add(self._nick)
        else:
            logger.warning(u"User %s is attempting to rejoin channel %s" %
                (self._nick, channel))
            return

        # Send commands
        self.command('JOIN', None, channel, prefix=self._fullname)
        self.do_names(channel)

    def on_privmsg(self, prefix, args):
        """Process received PRIVMSG command"""
        assert(len(args) == 2 and args[0])
        message = IRCMessage(self._nick, args[0], args[1])
        logger.info(u"%s says on %s: %s" %
            (self._nick, message.channel, message.text))
        self.server.display_queue.put(message)

    def on_quit(self, prefix, args):
        """Process received QUIT command"""
        logger.info(u"%s quits" % self._nick)
        self._quit = True

    def command(self, cmd, arg1, arg2, prefix=None):
        """Send a command back to the client"""
        line = ":%s %s%s%s" % (
            (prefix if prefix else self.server.name),
            (cmd if type(cmd) is str else u"%03d" % cmd),
            (u" " + arg1 if arg1 else u""),
            (u" :" + arg2 if arg2 else u""))
        self.wfile.write(line + u"\r\n")

    def do_names(self, channel):
        """Send nicks of users on the specified channel"""
        # 353 = namreply
        self.command(353, u"%s = %s" % (self._nick, channel),
            u" ".join(self._chans[channel]))
        # 366 = endofnames
        self.command(366, u"%s %s" % (self._nick, channel),
            u"End of /NAMES list.")

    def do_welcome(self):
        """Send welcoming messages"""
        assert(self._username and self._nick)
        self._fullname = (u"%s!%s@%s" %
            (self._nick, self._username, self.client_address[0]))
        logger.info(u"Welcoming %s" % self._fullname)
        # Welcome
        self.command(1, self._nick, u"Welcome on this dummy IRC server")
        # Your host
        self.command(2, self._nick, u"Your host is %s %s" %
            (self.server.name, SERVER_VERSION))
        self.command('NOTICE', self._nick, u"Your host is %s%s" %
           (self.server.name, SERVER_VERSION))
        # Created
        self.command(3, self._nick, u"This server was created a long time ago")
        # My info
        self.command(4, u"%s %s %s" %
            (self._nick, SERVER_VERSION, SERVER_INFO), None)
        # Feature list
        self.command(5, u"%s NETWORK=Testing" % self._nick,
            u"are available on this server")
        # User mode
        self.command('MODE', self._nick, u"+i", prefix=self._nick)

    def handle(self):
        """Handle an IRC session"""
        # Initialise internal state
        self._nick = None
        self._username = None
        self._fullname = None
        self._chans = dict()
        self._quit = False

        # First message
        self.command('NOTICE', 'AUTH',
            u"*** Please wait while I process your data")

        for line in self.rfile:
            line = line.strip()
            if line:
                logger.debug(u"Received line \"%s\"" % line)
                self.dispatch_command(line)
            if self._quit:
                return


class IRCServer(SocketServer.ThreadingTCPServer):
    """Simple IRC server for testing purpose"""

    # Allow reuse of an address, as dirong testing the server is fast restarted
    allow_reuse_address = True

    def __init__(self, address, name):
        """Start an IRC server on give address with the specified name"""
        self.name = name
        self.display_queue = Queue.Queue()
        logger.info(u"Starting server %s on %s:%d" %
            (name, address[0], address[1]))
        SocketServer.TCPServer.__init__(self, address, _IRCServerHandler)


class IRCServerThread(threading.Thread):
    """Thread where an IRCServer runs"""

    def __init__(self, *args, **kwargs):
        self.srv = IRCServer(*args, **kwargs)
        super(IRCServerThread, self).__init__()

    def run(self):
        self.srv.serve_forever()

    def get_displayed_message(self, timeout):
        """Get next displayed message, or None if time goes out

        Return an IRCMessage
        """
        try:
            return self.srv.display_queue.get(timeout=timeout)
        except Queue.Empty:
            return None


class IRCMessage(object):
    """An IRC message is a (user, channel, text) tuple"""

    def __init__(self, user, channel, text):
        self.user = user
        self.channel = channel
        self.text = text


def main(argv):
    """Start server"""
    # Parse command line
    parser = optparse.OptionParser(usage="usage: %prog [options]")
    parser.add_option('-H', '--host', action='store', dest='host',
        help=u"Litening host", metavar="HOST",
        default=u"localhost")
    parser.add_option('-p', '--port', action='store', dest='port',
        help=u"Litening port", metavar="PORT",
        default=u"6667")
    parser.add_option('-N', '--name', action='store', dest='name',
        help=u"Server name", metavar="SERVER_NAME",
        default=u"irc.localdomain")

    opts, argv = parser.parse_args(argv)
    address = (opts.host, int(opts.port))
    srv = IRCServer(address, opts.name)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        # Exit normally
        pass

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S')
    main(sys.argv)
