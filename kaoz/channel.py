# -*- coding: utf-8 -*-
# Copyright © 2011-2013 Binet Réseau
# See the LICENCE file for more informations

# This file is a part of Kaoz, a free irc notifier

# Useful function to differentiate nick and channel names
from irc.client import is_channel


class ChanStatus(object):
    """A simple structure which holds information about a channel

    Note that this structure is not thread-safe
    """

    def __init__(self, name):
        self.name = name
        self.is_joined = False
        self.join_attemps = 0
        self.messages = list()

    def mark_joined(self):
        """Mark this channel as joined"""
        self.is_joined = True
        self.join_attemps = 0

    def need_join_and_try(self):
        """Return True if this channel needs to be joined.
        Increase the join counter
        """
        need_join = is_channel(self.name) and not self.is_joined
        if need_join:
            self.join_attemps = self.join_attemps + 1
        return need_join


class IndexedChanDict(dict):
    """Dictionary of ChanStatus with an index.

    The index is used when saying messages on IRC, to remember the next channel
    to take into account.
    """

    def __init__(self):
        # channel name => ChanStatus mapping
        super(IndexedChanDict, self).__init__()
        # Ordered channel names, to be used when running a loop
        self._list = list()

    def __getitem__(self, channel):
        """Get a ChanStatus or create a new one if it does not exist"""
        if channel not in self:
            self[channel] = ChanStatus(channel)
        return super(IndexedChanDict, self).__getitem__(channel)

    def __setitem__(self, channel, status):
        """Set a specific ChanStatus"""
        if channel not in self:
            self._list.append(channel)
        return super(IndexedChanDict, self).__setitem__(channel, status)

    def __delitem__(self, channel):
        """Delete a channel status"""
        super(IndexedChanDict, self).__delitem__(channel)
        self._list.remove(channel)

    def leave(self, channel):
        """Remove given channel due to a kick or a part"""
        if channel not in self:
            return
        self[channel].is_joined = False
        if not self[channel].messages:
            del self[channel]

    def leave_all(self):
        """Leave every channel"""
        # Use list(self) because self dict is modified by leave
        for channel in list(self):
            self.leave(channel)

    def find_waiting_channel(self):
        """Find a channel which has messages waiting to be sent, or None"""
        for (i, channel) in enumerate(self._list):
            if self[channel].messages:
                self._list = self._list[(i+1):] + self._list[0:i+1]
                return self[channel]
        return None
