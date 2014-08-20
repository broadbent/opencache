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
        """Represents calls made to the Floodlight's Static Flowpusher API."""

        def __init__(self, host, port):
            """Initialise object with hostname and port of Floodlight controller."""
            self.host = host
            self.port = port

        def get(self, data):
            """Send HTTP GET request to Floodlight API."""
            ret = self._rest_call({}, 'GET')
            return json.loads(ret[2])

        def set(self, data):
            """Send HTTP POST request to Floodlight API."""
            ret = self._rest_call(data, 'POST')
            return ret[0] == 200

        def remove(self,data):
            """Send HTTP DELETE request to Floodlight API."""
            ret = self._rest_call(data, 'DELETE')
            return ret[0] == 200

        def _rest_call(self, data, action):
            """Send REST call to Floodlight controller's Static Flowpusher API."""
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
            conn.close()
            return ret

    class Device:
        """Represents calls made to the Floodlight's Device API."""

        def __init__(self, host, port):
            """Initialise object with hostname and port of Floodlight controller."""
            self.host = host
            self.port = port

        def get(self, data):
            """Send HTTP GET request to Floodlight API."""
            ret = self._rest_call(data, 'GET')
            result = json.loads(ret[2])
            if result != []:
                try:
                    port = str(result[0]['attachmentPoint'][0]['port'])
                    dpid = str(result[0]['attachmentPoint'][0]['switchDPID'])
                    mac = str(result[0]['mac'][0])
                except IndexError:
                    raise
                try:
                    vlan = str(result[0]['vlan'][0])
                except:
                    vlan = '-1'
                return (port, dpid, mac, vlan)
            else:
                raise KeyError

        def _rest_call(self, data, action):
            """Send REST call to Floodlight controller's Device API."""
            path = '/wm/device/?ipv4=' + data
            conn = httplib.HTTPConnection(self.host, self.port)
            conn.request('GET', path)
            response = conn.getresponse()
            ret = (response.status, response.reason, response.read())
            conn.close()
            return ret

    def add_redirect(self, expr, node_host, node_port, openflow_host, openflow_port):
        """Add a redirect for content requests matching given expression to a given node."""
        pusher = self.StaticFlowEntryPusher(openflow_host, openflow_port)
        device = self.Device(openflow_host, openflow_port)
        try:
            (_, connected_dpid, node_mac, node_vlan) = device.get(node_host)
        except KeyError:
            raise
        request_hands_off = {
            "switch": connected_dpid,
            "name": "request_hands_off-" + node_host + "-" + node_port + "-" + expr,
            "priority": "32767",
            "ether-type": 0x0800,
            "protocol": 0x06,
            "src-ip": node_host,
            "src-mac": node_mac,
            "dst-ip": expr,
            "dst-port":"80",
            "vlan-id":node_vlan,
            "active":"true",
            "actions":"output=normal"
        }
        request_in = {
            "switch": connected_dpid,
            "name": "request_in-" + node_host + "-" + node_port + "-" + expr,
            "priority": "32766",
            "ether-type": 0x0800,
            "protocol": 0x06,
            "dst-ip": expr,
            "dst-port": "80",
            "vlan-id":node_vlan,
            "active": "true",
            "actions": "set-dst-mac=" + node_mac + ",set-dst-ip=" + node_host +
                ",set-dst-port=" + node_port +",output=normal"
        }
        request_out = {
            "switch": connected_dpid,
            "name": "request_out-" + node_host + "-" + node_port + "-" + expr,
            "cookie": "0",
            "priority": "32766",
            "ether-type": 0x0800,
            "protocol": 0x06,
            "src-ip": node_host,
            "src-mac": node_mac,
            "src-port": node_port,
            "vlan-id":node_vlan,
            "active": "true",
            "actions": "set-src-port=80,set-src-ip=" + expr + ",output=normal"
        }
        pusher.remove({"name":"request_hands_off-" + node_host + "-" + node_port + "-" + expr})
        pusher.remove({"name":"request_out-" + node_host + "-" + node_port + "-" + expr})
        pusher.remove({"name":"request_in-" + node_host + "-" + node_port + "-" + expr})
        pusher.set(request_hands_off)
        pusher.set(request_out)
        pusher.set(request_in)

    def remove_redirect(self, expr, node_host, node_port, openflow_host, openflow_port):
        """Remove a redirect for content requests matching given expression to given node."""
        pusher = self.StaticFlowEntryPusher(openflow_host, openflow_port)
        pusher.remove({"name":"request_hands_off-" + node_host + "-" + node_port + "-" + expr})
        pusher.remove({"name":"request_out-" + node_host + "-" + node_port + "-" + expr})
        pusher.remove({"name":"request_in-" + node_host + "-" + node_port + "-" + expr})
