#!/usr/bin/env python2.7

"""http-client.py: HTTP Client - makes a GET request for content."""

import httplib
import time

myList=['/one.txt', '/two.txt', '/three.txt']

i = 0

while True:
    for e in myList:
        try:
            i += 1
            conn = httplib.HTTPConnection("127.0.0.1:49003")
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
