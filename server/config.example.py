#!/usr/bin/python
# -*- coding: utf-8 -*-

#This file is a part of Kaoz, a free irc notifier
#Copyright © Binet Réseau, see the licence file for more informations

# IRC SPECIFIC PARAMETERS
NICK = 'KaozNotifier' #The nickname in nickname!username@host:realname
USER_NAME = 'Kaoz' #The username
REAL_NAME = 'Kaoz is notifying the world' #The realname
IRC_SERVER = 'irc.myircnetwork.tld' #The dns or ip of the server to connect to
IRC_PORT = 6667 #IRC port. Usually 6667 unless SSL is used.
IRC_SERVER_PASSWORD = None #If there is a global server password
SSL_IRC = False #Turn to True if there is SSL support on this server on the port you specified.

# LISTENER PARAMETERS
LISTENER_PORT = 9010 #Port to Listen for transmitting messages
LISTENER_PASSWORD = 'MyVerySecretPassword' #Password to provide in order to send a line
LISTENER_SSL = True #Turn to False if you do not wish the listener to use ssl
LISTENER_PEM = '/etc/ssl/kaoz/server.pem' #The path to your .pem file is you said True above. It should contain the certificate and the key in one file.
