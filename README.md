Kaoz
====

==General purpose==
Kaoz is a free notifier for IRC. It's purpose is to provide an easy to use way for System Administrators to send warnings and logs on any choosen IRC channel.
It therefore uses a persistent daemon that will listen on a given port, optionnaly with ssl enabled, and will expect lines to have the format `password:#channel:Message`.
Password is a global password required to use the service.
channel is an irc channel on the configured network. (Kaoz will join the channel to do so)
The Message can be any given string. Please be sure that your line is not too long since it may be shortened out by the IRC server (Kaoz performs no checks)

==Licence==
Kaoz is provided under a MIT-like licence. See the licence file for more informations.

==Installation==
First, copy the config (`cp config.example.py config.py`) and edit the config.py file to provide correct values for the IRC Server and the listening socket
Then, change starter.sh to reflect the correct installation path of Kaoz.
Run starter.sh, and enjoy !

==Known limitations==
* Kaoz does not support key-protected channels

==Contact==
Kaoz is provided by "Binet Réseau", a student association from France's Ecole polytechnique.
If you have inquiries, comments or suggestions, you may contact us at br@eleves.polytechnique.fr
