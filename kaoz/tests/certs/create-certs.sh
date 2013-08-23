#!/bin/sh
# Create some certificates

FILENAME="kaoz-example"
KEYFILE="$FILENAME.key"
CRTFILE="$FILENAME.crt"

openssl req -new -x509 -newkey rsa:1024 -keyout "$KEYFILE" -out "$CRTFILE" -days 3650 -utf8 -nodes -config openssl.cnf && \
openssl x509 -noout -text -in "$CRTFILE"
