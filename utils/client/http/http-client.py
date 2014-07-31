#!/usr/bin/env python2.7

"""http-client.py: HTTP Client - makes a GET request for content."""

import httplib
import time
import sys
import socket
import signal
import os

myList=['/one.txt', '/two.txt', '/three.txt']

i = 0

try:
    socket.inet_aton(sys.argv[1])
except (IndexError, socket.error):
    print 'provide a valid IP address'
    sys.exit(2)

def hard_exit(signum, frame):
    os.kill(os.getpid(), signal.SIGKILL)

signal.signal(signal.SIGINT, hard_exit)

while True:
    for e in myList:
        try:
            i += 1
            conn = httplib.HTTPConnection(sys.argv[1])
            conn.request("GET", e)
            r1 = conn.getresponse()
            #print r1.status, r1.reason
            data1 = r1.read()
            if data1:
                print data1
            conn.close()
            time.sleep(1)
        except:
            pass
