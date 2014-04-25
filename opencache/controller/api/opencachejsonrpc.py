#!/usr/bin/env python2.7     

"""opencachejson.py - Implements a JSON-RPC interface for communicating with the controller. """

import BaseHTTPServer
import json
import multiprocessing
import SocketServer

import opencache.lib.opencachelib as lib

TAG = 'api'

class Api:

    _server_proc = None
    _server = None
    _config = None
    _controller = None

    def __init__(self, controller, config):
        """Initialise API instance with useful objects.

        Instantiated controller and configuration objects are passed for use within this instance.

        """
        self._controller = controller
        self._config = config
        HandlerClass = JSONHandler
        HandlerClass.protocol_version = "HTTP/1.0"
        HandlerClass.controller = self._controller
        self._server = ThreadedHTTPServer((self._config['controller_host'], int(self._config['controller_port'])), HandlerClass)
        self._server_proc = multiprocessing.Process(target=self._create_server, args=())
        self._server_proc.start()

    def stop(self):
        """Stop JSON server."""
        try:
            self._server.socket.close()
            self._server.server_close()
            self._server_proc.terminate()
        except Exception:
            pass

    def _create_server(self):
        """Start JSON Server."""
        self._controller.print_info(TAG, "JSON-RPC API starting at %s:%s" %(self._config['controller_host'], self._config['controller_port']))
        self._server.serve_forever()

class ThreadedHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """Create a threaded HTTP server."""
    allow_reuse_address = True
    daemon_threads = True

class JSONHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    
    class _RemoteProcedureCall():
        """Simple object used to store RPC information."""
        
        def __init__(self):
            """Initialise object with deault values."""
            self.expr = '*'
            self.node_id = '*'
            self.id = 0

    def log_message( self, format, *args ):
        """Ignore log messages."""
        pass

    def do_GET(self):
        """Ignore GET messages."""
        pass

    def _validate_request(self, rpc):
        try:
            if "id" not in rpc.request:
                raise Exception
            else:
                rpc.id = str(rpc.request["id"])
            if "method" not in rpc.request or "params" not in rpc.request or "jsonrpc" not in rpc.request:
                raise Exception
            else:
                rpc.method = str(rpc.request["method"])
                rpc.params = rpc.request["params"]
            return rpc
        except Exception:
            raise lib.RemoteProcedureCallError(data='The JSON sent is not a valid Request object.', code='-32600')

    def _validate_method_params(self, rpc):
        try:
            if rpc.method == 'hello':
                if "host" in rpc.params and "port" in rpc.params:
                    rpc.host = str(rpc.params["host"])
                    rpc.port = str(rpc.params["port"])
                else:
                    raise Exception
            elif rpc.method == "keep_alive" or rpc.method == "goodbye":
                if "node-id" in rpc.params:
                    rpc.node_id = str(rpc.params["node-id"])
                else:
                    raise Exception
            else:
                if "node-id" in rpc.params:
                    rpc.node_id = str(rpc.params["node-id"])
                if "expr" in rpc.params:
                    rpc.expr = str(rpc.params["expr"])
            return rpc
        except Exception:
            raise lib.RemoteProcedureCallError(data='Invalid method parameter(s).', code='-32602')

    def _call_method(self, rpc):
        try:
            result = getattr(self.controller, rpc.method)(rpc)
            return result
        except AttributeError:
            raise lib.RemoteProcedureCallError(data=('Controller has no method named: %s' % rpc.method), code='-32601')

    def do_POST(self):
        """Handle POST message containing JSON request."""
        header = self.headers.getheader('content-type')
        if header == 'application/x-www-form-urlencoded':
            try:
                content_length = int(self.headers.getheader('content-length'))
                post_body = self.rfile.read(content_length).decode('utf-8')
                self.controller.print_debug(TAG,  'post body: ' + str(post_body))
                rpc = self._RemoteProcedureCall()
                rpc.request = json.loads(post_body)
                rpc = self._validate_request(rpc)
                rpc.params = rpc.request['params']
                rpc = self._validate_method_params(rpc)
                result = self._call_method(rpc)
                lib.send_json_rpc_result(self, rpc.id, result)
            except lib.RemoteProcedureCallError as exception:
                lib.send_json_rpc_error(self, rpc.id, exception.code, exception.data)
