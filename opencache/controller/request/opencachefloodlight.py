#!/usr/bin/env python2.7

"""opencachefloodlight.py - Sends JSON-RPC commands to the Floodlight controller."""

import opencache.lib.opencachelib as lib
import urllib2
import json

TAG = 'request'

class Request:

    _config = None
    _controller = None

    def __init__(self, controller):
        """Initialise redirection instance with useful objects.

        Instantiated controller and configuration objects are passed for use within this instance.

        """
        self._controller = controller

    def stop(self):
        """Stop redirection object."""
        pass

    def add_redirect(self, expr, node_host, node_port, openflow_host, openflow_port):
        """Add a redirect for content requests matching given expression to given node."""
        port = ''
        dpid = ''
        vlan = ''
        try:
            url = 'http://' + openflow_host + ':' + openflow_port + '/wm/device/?ipv4=' + node_host
            response = json.loads(urllib2.urlopen(url).read())
            port = str(response[0]['attachmentPoint'][0]['port'])
            dpid = str(response[0]['attachmentPoint'][0]['switchDPID'])
            vlan = str(response[0]['vlan'][0])
        except Exception as e:
            self._controller.print_error(TAG, "Could not retrieve node attachment point from Floodlight: " + str(e))
        print port, dpid, vlan
        try:
            request_out = '{"switch": "' + dpid + '", "name":"' + node_host + '-' + node_port + '-' + expr + '-out", "cookie":"0", "priority":"32768", "active":"true", "ether-type":"2048", "vlan":"' + vlan + '", "protocol":"6", "src-ip":"' + node_host + '", "src-port":"' + node_port + '", "actions":"set-src-ip=' + expr + ',set-src-port=80,output=normal"}'
            print lib.do_json_rest_post(host=openflow_host, port=openflow_port, _json=request_out, path='/wm/staticflowentrypusher/json')
            request_in = '{"switch": "' + dpid + '", "name":"' + node_host + '-' + node_port + '-' + expr + '-in", "cookie":"0", "priority":"32768", "active":"true", "ether-type":"2048",  "vlan":"' + vlan + '", "protocol":"6", "dst-ip":"' + expr + '", "dst-port":"80", "ingress-port":"' + port + '", "actions":"set-dst-ip=' + node_host + ',set-dst-port=' + node_port + ',output=' + port + '"}'
            print lib.do_json_rest_post(host=openflow_host, port=openflow_port, _json=request_in, path='/wm/staticflowentrypusher/json')
        except Exception as e:
            self._controller.print_error(TAG, "Could not add redirect with Floodlight controller: " + str(e))

    def remove_redirect(self, expr, node_host, node_port, openflow_host, openflow_port):
        """Remove a redirect for content requests matching given expression to given node."""
        try:
            request_out = '{"name":"' + node_host + '-' + node_port + '-' + expr + '-out"}'
            print lib.do_json_rest_delete(host=openflow_host, port=openflow_port, _json=request_out, path='/wm/staticflowentrypusher/json')
            request_in = '{"name":"' + node_host + '-' + node_port + '-' + expr + '-in"}'
            print lib.do_json_rest_delete(host=openflow_host, port=openflow_port, _json=request_in, path='/wm/staticflowentrypusher/json')
        except Exception as e:
            self._controller.print_error(TAG, "Could not remove redirect with Floodlight controller: " + str(e))
