Kaoz
====

General purpose
---------------

Kaoz is a free notifier for IRC. It's purpose is to provide an easy to use way for System Administrators to send warnings and logs on any choosen IRC channel.
It therefore uses a persistent daemon, which is called the 'server' later on,  that will listen on a given port, optionnaly with ssl enabled, and will expect lines to have the format `password:#channel:Message`.
Password is a global password required to use the service.
channel is an irc channel on the configured network. (Kaoz will join the channel to do so)
In order to simplify the usage of the daemon, we are providing some of the scripts we found useful for correctly generating messages, thus refered as the 'clients'. This is completly optional, tough.
Please not that, in case you whish to agregate many servers' notifications, you can have only one Kaoz server, but you should duplicate client scripts.

Licence
-------

Kaoz is provided under a MIT-like licence. See the licence file for more informations.

Dependencies
------------
* python
* python openssl librairies (if you whish to use SSL)
* twisted
* socat (for ircpipe)

Installation of the server
--------------------------

First, copy the config (`cp config.example.py config.py`) and edit the config.py file to provide correct values for the IRC Server and the listening socket.
Then, change starter.sh to reflect the correct installation path of Kaoz.
Run starter.sh, and enjoy ! You might want to eventually create a init.d script instead, but it shouldn't be hard to figure out.

Known limitations
-----------------

* Kaoz does not support key-protected channels
* Kaoz does not check messages for oversized lines therefore, long lines may be cut by the IRC server.

Installing clients
------------------
We are providing in the 'client' directory several scripts that can help you getting started with generating messages for Kaoz to send.
We recommand that you put every one of those scripts in a shared directory. The first lines of each script are to be customized to match the server config.
Here is a quick overview of the features :
<dl>
<dt>ircpipe</dt>
<dd>This tool allow you to use the pipe operator to send messages to Kaoz. Please note that since it contains Kaoz's password, it is rather sensible. All our scripts depend on it. Please note the stdirc script, which should be in the same directory, and is used to provide colors to the messages.</dd>
<dt>nagios-ircpipe</dt>
<dd>A simple formater for nagios, a popular service monitoring tool.</dd>
<dt>nut-upsalert-ircpipe</dt>
<dd>A simple formater for NUT, a popular UPS monitoring tool.</dd>
<dt>pam</dt>
<dd>The login, rooting and fallback scripts can be use with a matching pam.d config to log login, su/sudo, or a special event (here, it is called by pam in case there is a problem with out physical token authentification server, but it could be anything you want to log). You will find in the etc-pam.d subdirectory a working sample configuration. However, it should be adapted to fit your specific pam.d.</dd>
</dl>

Contact
-------

Kaoz is provided by "Binet Réseau", a student association from France's Ecole polytechnique.
If you have inquiries, comments or suggestions, you may contact us at br@eleves.polytechnique.fr

<pre>
                 ________________
               _/ ______________ \_
             _/ _/              \_ \
            / _/   ____    ____   \ \
           / /    / __ \  / __ \   | |
          / /    / /_/ / / /_/ /   | |
          | |   / _, <  / _, _/    | |
          | |  / /_/ / / / | |     | |
          | | /_____/ /_/  | |    / /
           \ \              \ \__/ /
            \ \_             \____/
             \_ \________________
               \________________/

</pre>
