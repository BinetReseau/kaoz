#!/bin/sh
# Create some certificates

FILENAME="kaoz-example"
KEYFILE="$FILENAME.key"
CSRFILE="$FILENAME.csr"
CRTFILE="$FILENAME.crt"

openssl req -new -newkey rsa:1024 -keyout "$KEYFILE" -out "$CSRFILE" -days 3650 -utf8 -nodes -config openssl.cnf && \
openssl x509 -req -days 3650 -in "$CSRFILE" -signkey "$KEYFILE" -outform PEM -out "$CRTFILE" && \
rm "$CSRFILE" && \
openssl x509 -noout -text -in "$CRTFILE"

