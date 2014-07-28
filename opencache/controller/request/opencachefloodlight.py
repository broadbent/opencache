#!/usr/bin/env python2.7

"""opencachefloodlight.py - Sends JSON-RPC commands to the Floodlight controller."""

import opencache.lib.opencachelib as lib
import httplib
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

    class StaticFlowEntryPusher:

        def __init__(self, host, port):
            self.host = host
            self.port = port

        def get(self, data):
            ret = self._rest_call({}, 'GET')
            return json.loads(ret[2])

        def set(self, data):
            ret = self._rest_call(data, 'POST')
            return ret[0] == 200

        def remove(self,data):
            ret = self._rest_call(data, 'DELETE')
            return ret[0] == 200

        def _rest_call(self, data, action):
            path = '/wm/staticflowentrypusher/json'
            headers = {
                'Content-type': 'application/json',
                'Accept': 'application/json',
                }
            body = json.dumps(data)
            conn = httplib.HTTPConnection(self.host, self.port)
            conn.request(action, path, body, headers)
            response = conn.getresponse()
            ret = (response.status, response.reason, response.read())
            print ret
            conn.close()
            return ret

    class Device:

        def __init__(self, host, port):
            self.host = host
            self.port = port

        def get(self, data):
            path = '/wm/device/?ipv4=' + data
            conn = httplib.HTTPConnection(self.host, self.port)
            conn.request('GET', path)
            response = json.loads(conn.getresponse().read())
            port = str(response[0]['attachmentPoint'][0]['port'])
            dpid = str(response[0]['attachmentPoint'][0]['switchDPID'])
            mac = str(response[0]['mac'][0])
            return (port, dpid, mac)


    def add_redirect(self, expr, node_host, node_port, openflow_host, openflow_port):
        """Add a redirect for content requests matching given expression to given node."""
        pusher = self.StaticFlowEntryPusher(openflow_host, openflow_port)
        device = self.Device(openflow_host, openflow_port)
        (_, connected_dpid, node_mac) = device.get(node_host)
        request_in = {
            'switch':connected_dpid,
            "name":"request_in-" + node_host + "-" + node_port + "-" + expr,
            "cookie":"0",
            "priority":"32768",
            "ether-type":0x0800,# 0x800 x8100 all vald id packets
            "protocol":0x06, #TCP 0x06, ICMP 0x01 UDP 0x11
        #    "src-ip":"10.0.0.4",
        #    "src-mac":"2a:5a:bc:e9:30:a2",
            "dst-ip":expr,
        #   "dst-mac":"f2:1b:62:db:17:bd",
            "dst-port":"80",
            "active":"true",
            "actions":"set-dst-mac=72:25:c2:7c:38:fe,set-dst-ip=" + node_host +
                ",set-dst-port=" + node_port +",output=normal"
        }
        request_out = {
            'switch':connected_dpid,
            "name":"request_out-" + node_host + "-" + node_port + "-" + expr,
            "cookie":"0",
            "priority":"32768",
            "ether-type":0x0800,# 0x800 x8100 all vald id packets
            "protocol":0x06, #TCP 0x06, ICMP 0x01 UDP 0x11
            "src-ip":node_host,
            "src-mac":node_mac,
        #    "dst-ip":"10.0.0.4",
        #    "dst-mac":"2a:5a:bc:e9:30:a2",
            "src-port":node_port,
            "active":"true",
            "actions":"set-src-port=80,set-src-ip=" + expr + ",output=normal"
        }
        pusher.remove({"name":"request_out-" + node_host + "-" + node_port + "-" + expr})
        pusher.remove({"name":"request_in-" + node_host + "-" + node_port + "-" + expr})
        pusher.set(request_out)
        pusher.set(request_in)

    def remove_redirect(self, expr, node_host, node_port, openflow_host, openflow_port):
        """Remove a redirect for content requests matching given expression to given node."""
        pusher = self.Floodlight(openflow_host, openflow_port)
        pusher.remove({"name":"request_out-" + node_host + "-" + node_port + "-" + expr})
        pusher.remove({"name":"request_in-" + node_host + "-" + node_port + "-" + expr})
