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
import re
import threading
import sys

if sys.version_info < (3,):
    import Queue as queue
    import SocketServer as socketserver
else:
    import queue
    import socketserver

logger = logging.getLogger(__name__)

_rfc_1459_command_regexp = re.compile(
    r'^(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( *(?P<argument> .+))?')

SERVER_VERSION = "test-ircserver-0.0.1alpha"
SERVER_INFO = "aAbcCdefFghHiIjkKmnoOrRsvwxXy bceiIjklLmMnoOprRstv"


class _IRCServerHandler(socketserver.StreamRequestHandler):
    """Manage a request from TCP listener module"""

    def parse_command(self, line):
        """Parse next line sent by the client"""
        m = _rfc_1459_command_regexp.match(line)
        if not m:
            raise IOError("Received invalid line: %s" % line)
        args = []
        if m.group('argument'):
            a = m.group('argument').split(" :", 1)
            args = a[0].split()
            if len(a) == 2:
                args.append(a[1])

        return (m.group('prefix'), m.group('command').upper(), args)

    def dispatch_command(self, line):
        """Dispatch a received line among handlers"""
        (prefix, cmd, args) = self.parse_command(line)
        logger.debug("Dispatch (%s, %s, %s)" % (prefix, cmd, args))
        m = "on_" + cmd.lower()
        if hasattr(self, m):
            getattr(self, m)(prefix, args)
        else:
            logger.warning("No handler for command %s" % cmd)

    def on_nick(self, prefix, args):
        """Process received NICK command"""
        assert len(args) >= 1 and args[0]
        self._nick = args[0]
        # Test ""nick already in use" error case
        if self._nick.endswith('already-in-use'):
            self.command(433, "%s %s" % ("*", self._nick),
                         "Nickname is already in use.")
            logger.info("Nick %s is already in use" % self._nick)
            self._quit = True
            return

        if self._username:
            self.do_welcome()

    def on_user(self, prefix, args):
        """Process received USER command"""
        assert len(args) >= 1 and args[0]
        self._username = args[0]
        if self._nick:
            self.do_welcome()

    def on_join(self, prefix, args):
        """Process received JOIN command"""
        assert len(args) >= 1 and args[0]
        channel = args[0]
        if channel.startswith('#unjoinable'):
            logger.info("%s tried to join unjoinable channel %s" %
                        (self._nick, channel))
            return
        if channel not in self._chans:
            logger.info("Create channel %s with user %s" %
                        (channel, self._nick))
            self._chans[channel] = set([self._nick])
        elif self._nick not in self._chans[channel]:
            logger.info("User %s joins channel %s" % (self._nick, channel))
            self._chans[channel].add(self._nick)
        else:
            logger.warning("User %s is attempting to rejoin channel %s" %
                           (self._nick, channel))
            return

        # Send commands
        self.command('JOIN', None, channel, prefix=self._fullname)
        self.do_names(channel)

    def on_privmsg(self, prefix, args):
        """Process received PRIVMSG command"""
        assert len(args) == 2 and args[0]
        message = IRCMessage(self._nick, args[0], args[1])
        logger.info("%s says on %s: %s" %
                    (self._nick, message.channel, message.text))
        self.server.display_queue.put(message)

    def on_quit(self, prefix, args):
        """Process received QUIT command"""
        logger.info("%s quits" % self._nick)
        self._quit = True

    def command(self, cmd, arg1, arg2, prefix=None):
        """Send a command back to the client"""
        line = ":%s %s%s%s" % (
            (prefix if prefix else self.server.name),
            (cmd if type(cmd) is str else "%03d" % cmd),
            (" " + arg1 if arg1 else ""),
            (" :" + arg2 if arg2 else ""))
        try:
            self.wfile.write((line + "\r\n").encode('UTF-8'))
        except IOError:
            # May be BrokenPipeError
            if not self._quit:
                self._quit = True
                logger.info("IOError, %s quits" % self._nick)
            pass

    def do_names(self, channel):
        """Send nicks of users on the specified channel"""
        # 353 = namreply
        self.command(353, "%s = %s" % (self._nick, channel),
                     " ".join(self._chans[channel]))
        # 366 = endofnames
        self.command(366, "%s %s" % (self._nick, channel),
                     "End of /NAMES list.")

    def do_welcome(self):
        """Send welcoming messages"""
        assert self._username and self._nick
        self._fullname = (
            "%s!%s@%s" % (self._nick, self._username, self.client_address[0]))
        logger.info("Welcoming %s" % self._fullname)
        # Welcome
        self.command(1, self._nick, "Welcome on this dummy IRC server")
        # Your host
        self.command(2, self._nick, "Your host is %s %s" %
                     (self.server.name, SERVER_VERSION))
        self.command('NOTICE', self._nick,
                     "Your host is %s%s" % (self.server.name, SERVER_VERSION))
        # Created
        self.command(3, self._nick, "This server was created a long time ago")
        # My info
        self.command(4, "%s %s %s" % (self._nick, SERVER_VERSION, SERVER_INFO),
                     None)
        # Feature list
        self.command(5, "%s NETWORK=Testing" % self._nick,
                     "are available on this server")
        # User mode
        self.command('MODE', self._nick, "+i", prefix=self._nick)

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
                     "*** Please wait while I process your data")

        for line in self.rfile:
            line = line.strip().decode('utf-8')
            if line:
                logger.debug("Received line \"%s\"" % line)
                self.dispatch_command(line)
            if self._quit:
                return


class IRCServer(socketserver.ThreadingTCPServer):
    """Simple IRC server for testing purpose"""

    # Allow reuse of an address, as dirong testing the server is fast restarted
    allow_reuse_address = True

    def __init__(self, address, name):
        """Start an IRC server on give address with the specified name"""
        self.name = name
        self.display_queue = queue.Queue()
        logger.info("Starting server %s on %s:%d" %
                    (name, address[0], address[1]))
        socketserver.TCPServer.__init__(self, address, _IRCServerHandler)


class IRCServerThread(threading.Thread):
    """Thread where an IRCServer runs"""

    def __init__(self, *args, **kwargs):
        self.srv = IRCServer(*args, **kwargs)
        super(IRCServerThread, self).__init__()

    def run(self):
        self.srv.serve_forever()

    def stop(self):
        """Shut down server"""
        self.srv.shutdown()
        self.srv.server_close()
        self.join()

    def get_displayed_message(self, timeout):
        """Get next displayed message, or None if time goes out

        Return an IRCMessage
        """
        try:
            return self.srv.display_queue.get(timeout=timeout)
        except queue.Empty:
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
    parser.add_option(
        '-H', '--host', action='store', dest='host', default="localhost",
        help="Litening host", metavar="HOST")
    parser.add_option(
        '-p', '--port', action='store', dest='port', default="6667",
        help="Litening port", metavar="PORT")
    parser.add_option(
        '-N', '--name', action='store', dest='name', default="irc.localdomain",
        help="Server name", metavar="SERVER_NAME")

    opts, argv = parser.parse_args(argv)
    address = (opts.host, int(opts.port))
    srv = IRCServer(address, opts.name)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        # Exit normally
        pass

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S')
    main(sys.argv)
