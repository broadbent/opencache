#!/usr/bin/env python2.7

"""opencachefloodlight.py - Sends JSON-RPC commands to the Floodlight controller."""

import opencache.lib.opencachelib as lib

TAG = 'request'

class Request:

    _config = None
    _controller = None

    def __init__(self, controller, config):
        """Initialise redirection instance with useful objects.

        Instantiated controller and configuration objects are passed for use within this instance.

        """
        self._config = config
        self._controller = controller

    def stop(self):
        """Stop redirection object."""
        pass

    def add_redirect(self, expr, node_host, node_port, openflow_host, openflow_port, switch_dpid, vlan_id):
        """Add a redirect for content requests matching given expression to given node."""
        try:
            if expr == '*':
                _json = None
                _json = '{"switch": "' + switch_dpid + '", "name":"' + node_host + '-' + node_port + '-' + expr + '-fetch", "priority":"32767", "ether-type":"2048", "protocol":"6", "src-ip":"' + node_host + '", "dst-port":"80", "actions":"output=normal"}'
                print lib.do_json_rest_post(host=self._config['openflow_host'], port=self._config['openflow_port'], _json=_json, path='/wm/staticflowentrypusher/json')
                _json = None
                _json = '{"switch": "' + switch_dpid + '", "name":"' + node_host + '-' + node_port + '-' + expr + '-in", "' + switch_dpid + '", "priority":"32767", "ether-type":"2048", "protocol":"6", "dst-port":"80", "actions":"set-dst-ip=' + node_host + ',set-dst-port=' + node_port + ',output=normal"}'
                print lib.do_json_rest_post(host=self._config['openflow_host'], port=self._config['openflow_port'], _json=_json, path='/wm/staticflowentrypusher/json')
            else:
                _json = None
                _json = '{"switch": "' + switch_dpid + '", "name":"' + node_host + '-' + node_port + '-' + expr + '-out", "vlan-id":"' + vlan_id + '", "priority":"32767", "ether-type":"2048", "protocol":"6", "src-ip":"' + node_host + '", "src-port":"' + node_port + '", "actions":"set-src-ip=' + expr + ',set-src-port=80,output=normal"}'
                print lib.do_json_rest_post(host=self._config['openflow_host'], port=self._config['openflow_port'], _json=_json, path='/wm/staticflowentrypusher/json')
                _json = None
                _json = '{"switch": "' + switch_dpid + '", "name":"' + node_host + '-' + node_port + '-' + expr + '-fetch", "priority":"32767", "ether-type":"2048", "protocol":"6", "src-ip":"' + node_host + '", "dst-port":"80", "actions":"output=normal"}'
                print lib.do_json_rest_post(host=self._config['openflow_host'], port=self._config['openflow_port'], _json=_json, path='/wm/staticflowentrypusher/json')
                _json = None
                _json = '{"switch": "' + switch_dpid + '", "name":"' + node_host + '-' + node_port + '-' + expr + '-in", "priority":"32767", "ether-type":"2048", "protocol":"6", "dst-ip":"' + expr + '", "dst-port":"80", "actions":"set-dst-ip=' + node_host + ',set-dst-port=' + node_port + ',output=normal"}'
                print lib.do_json_rest_post(host=self._config['openflow_host'], port=self._config['openflow_port'], _json=_json, path='/wm/staticflowentrypusher/json')
        except Exception as e:
            self._controller.print_error(TAG, "Could not add redirect with Floodlight controller: " + str(e))

    def remove_redirect(self, expr, node_host, node_port, openflow_host, openflow_port, switch_dpid, vlan_id):
        """Remove a redirect for content requests matching given expression to given node."""
        try:
            _json = None
            _json = '{"name":"' + node_host + '-' + node_port + '-' + expr + '-out"}'
            print lib.do_json_rest_delete(host=self._config['openflow_host'], port=self._config['openflow_port'], _json=_json, path='/wm/staticflowentrypusher/json')
            _json = None
            _json = '{"name":"' + node_host + '-' + node_port + '-' + expr + '-fetch"}'
            print lib.do_json_rest_delete(host=self._config['openflow_host'], port=self._config['openflow_port'], _json=_json, path='/wm/staticflowentrypusher/json')
            _json = None
            _json = '{"name":"' + node_host + '-' + node_port + '-' + expr + '-in"}'
            print lib.do_json_rest_delete(host=self._config['openflow_host'], port=self._config['openflow_port'], _json=_json, path='/wm/staticflowentrypusher/json')
        except Exception as e:
            self._controller.print_error(TAG, "Could not remove redirect with Floodlight controller: " + str(e))
