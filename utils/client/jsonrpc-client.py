#!/usr/bin/env python2.7

"""opencache-client.py: simple command-line client to make requests to an OpenCache controller."""

import json
import optparse
import random
import urllib

def do_opencache_call(method, host, port, node, expr, call_id=None):
    """Make a JSON-RPC call to an OpenCache controller. Print and return the result."""
    if call_id == None:
        call_id = random.randint(1, 999)
    params = {'node' : str(node), 'expr' : str(expr)}
    url =  "http://%s:%s" % (host, port)
    try:
        post_data = json.dumps({"id":call_id, "method":str(method), "params":params, "jsonrpc":"2.0"})
    except Exception as exception:
        print "[ERROR] Could not encode JSON: %s" % exception
    try:
        response_data = urllib.urlopen(url, post_data).read()
        print "[INFO] Sent request: %s" %post_data
        try:
            response_json = json.loads(response_data)
            if response_json['id'] == str(call_id):
                print "[INFO] Received response: %s" %response_json
                return response_json
            else:
                print "[ERROR] Mismatched call ID for response: %s" %response_json
                raise IOError("Mismatched call ID for response: %s" %response_json)
        except Exception as exception:
            print "[ERROR] Could not decode JSON from OpenCache node response: %s" % exception
    except IOError as exception:
        print "[ERROR] Could not connect to OpenCache instance: %s" % exception

if __name__ == '__main__':
    """Read command line arguments."""
    parser = optparse.OptionParser()
    parser.add_option("-m", "--method", dest="method",
        help="method to call on OpenCache controller: start/stop/pause/stat/refresh")
    parser.add_option("-i", "--hostname", dest="host", default='127.0.0.1', 
        help="hostname of OpenCache controller")
    parser.add_option("-p", "--port", dest="port", default='49001',
        help="port number of the OpenCache JSON-RPC interface listening for requests")
    parser.add_option("-n", "--node", dest="node", default='*',
        help="list of nodes to execute given OpenCache command on")
    parser.add_option("-e", "--expression", dest="expr", default='*',
        help="list of expressions to execute with given OpenCache command")
    (options, args) = parser.parse_args()
    do_opencache_call(options.method, options.host, options.port, options.node, options.expr)