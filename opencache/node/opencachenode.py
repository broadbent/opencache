#!/usr/bin/env python2.7

"""opencachenode.py: OpenCache Node - handles requests from the controller to start/stop/pause/stat cache instances."""

import BaseHTTPServer
import collections
import httplib
import json
import multiprocessing
import optparse
import os
import signal
import SocketServer
import threading
import time

import hashlib
import configparser
import opencache.lib.opencachelib as lib
import opencache.node.server.opencachehttp as server
import opencache.node.state.opencachemongodb as database
import zmq

TAG = 'node'

allocated_port_number = collections.deque()
port_number_lock = threading.Lock()
server_dict = {}
object_dict = {}

class Node():

    node_id = None
    config = None
    ipc_socket = None

    _controller_communication = None
    _json_server = None

    def __init__(self, config_path):
        """Initialise node instance.

        Sets up signal handling to deal with interrupts. Loads configuration file, checks validity and creates
        sensible defaults if values missing. Starts loaded modules. Initialises logger to handle output durring
        running. Creates and binds socket for inter-process communications with server instances. Allocates
        potential ports for server instances. Starts continuous communication with controller. Starts JSON server
        ready to receive commands from the controller.

        """
        self._setup_signal_handling()
        self._option_check(config_path)
        parser = configparser.ConfigParser(delimiters='=')
        parser.read(config_path)
        self.config = self._create_config_defaults()
        self.config = lib.load_config(self.config, parser)
        lib.create_directory(self.config["cache_path"] + 'shared')
        self._logger = lib.setup_logger(self.config["log_path"], TAG, self.config["verbosity"])
        self.database = database.State(self)
        self._allocate_ports(self.config["port_range"])
        context = zmq.Context()
        self.ipc_socket = context.socket(zmq.PUB)
        self.ipc_socket.bind("ipc://oc")
        self._controller_communication = ControllerCommunication(self)
        self._json_server = JSONServer(self)

    def print_debug(self, tag, string):
        """Print a formatted error message if verbosity level permits."""
        lib.log_debug(tag, string)

    def print_info(self, tag, string):
        """Print a formatted information message if verbosity level permits."""
        lib.log_info(tag, string)

    def print_warn(self, tag, string):
        """Print a formatted warning message if verbosity level permits."""
        lib.log_warn(tag, string)

    def print_error(self, tag, string):
        """Print a formatted warning message if verbosity level permits."""
        lib.log_error(tag, string)

    def _option_check(self, config_path):
        if config_path == None:
            print ("Please specify a configuration file using '--config'. Exiting.")
            os._exit(3)

    def _create_config_defaults(self):
        """Load configuration defaults before loading the user's configuration"""
        config = dict()
        config['node_host'] = '127.0.0.1'
        config['node_port'] = '49002'
        config['notification_port'] = '50001'
        config['port_range'] = '49003,50000'
        config['controller_host'] = '127.0.0.1'
        config['controller_port'] = '49001'
        config['cache_path'] = '/var/tmp/opencache/'
        config['log_path'] = '/var/log/opencache/node'
        config['keep_alive_interval'] = '15'
        config['stat_refresh'] = '60'
        config['alert_load'] = '500'
        config['alert_disk'] = '9663676416'
        config['max_disk'] = '10737418240'
        config['stat_refresh'] = '60'
        config['verbosity'] = '3'
        return config

    def _setup_signal_handling(self):
        """Setup signal handling for SIGQUIT and SIGINT events"""
        signal.signal(signal.SIGINT, self._exit_node)
        signal.signal(signal.SIGQUIT, self._exit_node)

    def _exit_node(self, signal, frame):
        """Quit the OpenCache node gracefully"""
        self._stop()
        self.print_info(TAG, 'Caught exit signal: exiting OpenCache node')
        os._exit(1)

    def _allocate_ports(self, port_range):
        """Allocate ports that the node can use for new cache instances."""
        range_split = port_range.split(',')
        for port in range(int(range_split[0]), int(range_split[1])):
            allocated_port_number.append(port)

    def _stop(self):
        """Exit gracefully.

        Send a goodbye to controller and the stop command to all running servers.

        """
        self._controller_communication.send_goodbye_to_controller()
        getattr(RemoteProcedureCall,'stop')(self, {'expr' : '*'})

class RemoteProcedureCall():

    @staticmethod
    def start(node, params):
        """Create new cache instances or restart existing ones.

        Handle the three permutations of expression descriptions (all, list or single).
        If a server does not exist, create a new one. If a server does exist, send it the 'start'
        command to bring it out of a halted 'paused' state.

        Special case: If '*' (all) is given, then this will automatically override other servers,
        as it describes all traffic. As such, all other servers are paused, and a single new one
        created for the 'catch all'

        """
        try:
            if params["expr"] == '*':
                for expr in server_dict:
                    RemoteProcedureCall._pause_server(node, expr)
                if params["expr"] in server_dict:
                    RemoteProcedureCall._start_server(node, params["expr"])
                else:
                    RemoteProcedureCall._start_new_server(node, params["expr"])
            elif "|" in params["expr"]:
                for expr in params["expr"].split("|"):
                    if expr in server_dict:
                        RemoteProcedureCall._start_server(node, expr)
                    else:
                        RemoteProcedureCall._start_new_server(node, expr)
            else:
                if params["expr"] in server_dict:
                    RemoteProcedureCall._start_server(node, params["expr"])
                else:
                    RemoteProcedureCall._start_new_server(node, params["expr"])
        except lib.RemoteProcedureCallError:
            raise
        return True

    @staticmethod
    def _start_server(node, expr):
        """Instruct a single (existing) server to start."""
        root, path = lib.expr_split(expr)
        try:
            RemoteProcedureCall._send_to_server(node, root, 'start')
            node.print_info(TAG, "Existing server started with expr: %s" %expr)
        except Exception as e:
            node.print_error(TAG, "Error occured with 'start' command for expression '%s': %s" % (expr, e))
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(expr)}, code='-32603')

    @staticmethod
    def _start_new_server(node, expr):
        """Create a single (new) server.

        Use next available port to start server process. Store server process and port.

        """
        root, path = lib.expr_split(expr)
        try:
            try:
                port_number_lock.acquire()
                port = allocated_port_number.popleft()
                port_number_lock.release()
            except IndexError:
                node.print_error(TAG, "No ports remaining in allocation, cannot start new server.")
                return False
            process = multiprocessing.Process(target=server.Server, args=(node, root, port))
            process.daemon = True
            process.start()
            server_dict[expr] = {"process" : process, "port" : port}
            node.print_info(TAG, "New server started with expr: %s" %expr)
        except Exception as e:
            node.print_error(TAG, "Error occured with 'start' (new server) for expression '%s': %s" % (expr, e))
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(expr)}, code='-32603')

    @staticmethod
    def stop(node, params):
        """Stop running cache instances.

        Handle the three permutations of expression descriptions (all, list or single). Send each server
        the 'stop' command to halt operation. Once all servers are stopped, remove the servers from the node.

        """
        try:
            if params["expr"] == '*':
                server_dict_copy = list()
                for expr in server_dict:
                    RemoteProcedureCall._stop_server(node, expr)
                    server_dict_copy.append(expr)
                for expr in server_dict_copy:
                    del server_dict[expr]
                del server_dict_copy
            elif "|" in params["expr"]:
                server_dict_copy = list()
                for expr in params["expr"].split("|"):
                    RemoteProcedureCall._stop_server(node, expr)
                    server_dict_copy.append(expr)
                for expr in server_dict_copy:
                    del server_dict[expr]
                del server_dict_copy
            else:
                if params["expr"] in server_dict:
                    RemoteProcedureCall._stop_server(node, params["expr"])
                    del server_dict[params["expr"]]
        except lib.RemoteProcedureCallError:
            raise
        return True

    @staticmethod
    def _stop_server(node, expr):
        """Instruct single server to stop.

        Send stop command and then terminate process. Add port back to those available to new servers.

        """
        root, path = lib.expr_split(expr)
        try:
            RemoteProcedureCall._send_to_server(node, root, 'stop')
            time.sleep(0.1)
            server_dict[expr]["process"].terminate()
            port_number_lock.acquire()
            allocated_port_number.append(server_dict[expr]["port"])
            port_number_lock.release()
            node.print_info(TAG, "Server stopped with expr: %s" %expr)
        except Exception as e:
            node.print_error(TAG, "Error occured with 'stop' command for expression '%s': %s" % (expr, e))
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(expr)}, code='-32603')

    @staticmethod
    def pause(node, params):
        """Pause running cache instances.

        Handle the three permutations of expression descriptions (all, list or single).

        """
        try:
            if params["expr"] == '*':
                for expr in server_dict:
                    RemoteProcedureCall._pause_server(node, expr)
            elif "|" in params["expr"]:
                for expr in params["expr"].split("|"):
                    RemoteProcedureCall._pause_server(node, expr)
            else:
                if params["expr"] in server_dict:
                    RemoteProcedureCall._pause_server(node, params["expr"])
        except lib.RemoteProcedureCallError:
            raise
        return True

    @staticmethod
    def _pause_server(node, expr):
        """Instruct single server to pause."""
        root, path = lib.expr_split(expr)
        try:
            RemoteProcedureCall._send_to_server(node, root, 'pause')
            node.print_info(TAG, "Server paused with expr: %s" %expr)
        except Exception as e:
            node.print_error(TAG, "Error occured with 'pause' command for expression '%s': %s" % (expr, e))
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(expr)}, code='-32603')

    @staticmethod
    def stat(node, params):
        """Retrieve statistics from running cache instances.

        Handle the three permutations of expression descriptions (all, list or single).

        """
        try:
            if params["expr"] == '*':
                for expr in server_dict:
                    RemoteProcedureCall._stat_server(node, expr)
            elif "|" in params["expr"]:
                for expr in params["expr"].split("|"):
                    RemoteProcedureCall._stat_server(node, expr)
            else:
                if params["expr"] in server_dict:
                    RemoteProcedureCall._stat_server(node, params["expr"])
        except lib.RemoteProcedureCallError:
            raise
        return True

    @staticmethod
    def _stat_server(node, expr):
        """Instruct single server to return statistics to controller."""
        root, path = lib.expr_split(expr)
        try:
            RemoteProcedureCall._send_to_server(node, root, 'stat')
            node.print_info(TAG, "Server stat'ed with expr: %s" %expr)
        except Exception as e:
            node.print_error(TAG, "Error occured with 'stat' command for expression '%s': %s" % (expr, e))
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(expr)}, code='-32603')

    @staticmethod
    def seed(node, params):
        """Seed running cache instances.

        Handle the three permutations of expression descriptions (all, list or single).

        """
        transaction = RemoteProcedureCall._find_transaction(params["expr"])
        try:
            for expr in params["expr"].split("|"):
                RemoteProcedureCall._seed_server(node, expr, transaction)
        except lib.RemoteProcedureCallError:
            raise
        return True

    @staticmethod
    def _seed_server(node, expr, transaction):
        root, path = lib.expr_split(expr)
        object_dict[expr] = transaction
        try:
            key = hashlib.sha224(path).hexdigest()
            path = node.config["cache_path"] + 'shared/' + transaction
            node.database.create({'key' : key, 'path' : path})
            node.print_info(TAG, "Server seeded with expression: %s" %expr)
        except Exception as e:
            node.print_error(TAG, "Error occured with 'seed' command for expression '%s': %s" % (expr, e))
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(expr)}, code='-32603')

    @staticmethod
    def fetch(node, params):
        threading.Thread(target=RemoteProcedureCall._fetch_object, args=(node, params)).start()

    @staticmethod
    def _fetch_object(node, params):
        root, path = lib.expr_split(params['expr'])
        transaction = RemoteProcedureCall._find_transaction(params['expr'])
        object_path =  node.config["cache_path"] + 'shared/' + transaction
        connection = httplib.HTTPConnection(root)
        connection.request("GET", path)
        response = connection.getresponse()
        read_payload = response.read()
        connection.close()
        f = open(object_path, 'w')
        f.write(read_payload)
        f.close()
        object_dict[params['expr']] = transaction
        RemoteProcedureCall.seed(node, params)

    @staticmethod
    def _find_transaction(expr):
        for expr in expr.split("|"):
                if object_dict.has_key(expr):
                    return object_dict[expr]
        return os.urandom(28).encode('hex')

    @staticmethod
    def _send_to_server(node, expr, method, path='?', transaction='?'):
        node.ipc_socket.send_string("%s %s %s %s" % (expr.decode('ascii'), str(method), path.decode('ascii'), transaction.decode('ascii')))

class JSONServer():

    def __init__(self, node):
        """Create and start a JSON server ready to send and receive messages from the controller."""
        handler = HandlerClass
        server = ThreadedHTTPServer((node.config["node_host"], int(node.config["node_port"])), handler)
        server._node = node
        server.serve_forever()

class ThreadedHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """Create a threaded HTTP server."""
    allow_reuse_address = True
    daemon_threads = True

    _node = None

class HandlerClass(BaseHTTPServer.BaseHTTPRequestHandler):

    def log_message( self, format, *args ):
        """Ignore log messages."""
        pass

    def do_GET(self):
        """Ignore GET requests."""
        pass

    def do_POST(self):
        """Handle POST message containing JSON request from controller."""
        header = self.headers.getheader('content-type')
        if header == 'application/x-www-form-urlencoded':
            content_length = int(self.headers.getheader('content-length'))
            post_body = self.rfile.read(content_length)
            post_json = json.loads(post_body)
            message_id = post_json["id"]
            try:
                result = getattr(RemoteProcedureCall, post_json["method"])(self.server._node, post_json["params"])
                lib.send_json_rpc_result(self, message_id, result)
            except AttributeError:
                lib.send_json_rpc_error(self, message_id, '-32601', data=('Node has no method named: %s' % post_json["method"]))
            except lib.RemoteProcedureCallError as exception:
                lib.send_json_rpc_error(self, message_id, '-32603', data=exception)

class ControllerCommunication():

    _call_id = 0
    _reset = 0
    _node =  None

    def __init__(self, node):
        """Send intial 'hello' message."""
        self._node = node
        self._send_hello_to_controller()

    def _send_hello_to_controller(self):
        """Send initial 'hello' to controller.

        If a connection cannot be made to the controller, retry in 'n' seconds. 'n' is configured by
        the user in the configuration file.

        From the initial 'hello' message, a node ID is returned that is used in all communications.

        """
        data = {"host" : self._node.config["node_host"], "port" : self._node.config["node_port"]}
        while (self._node.node_id == None):
            try:
                self._call_id += 1
                response = lib.do_json_rpc_post(_id=self._call_id, method="hello", host=self._node.config["controller_host"], port=int(self._node.config["controller_port"]), _input=data)
                self._node.node_id = response["result"]["node-id"]
                self._node.print_info(TAG, 'OpenCache node connected to controller, given ID: %s' % self._node.node_id)
            except Exception:
                self._node.print_warn(TAG, ("Could not connect to controller, retrying in %s seconds." % self._node.config["keep_alive_interval"]))
                time.sleep(float(self._node.config["keep_alive_interval"]))
        threading.Timer(interval=int(self._node.config["keep_alive_interval"]), function=self._send_keep_alive_to_controller, args=()).start()

    def _send_keep_alive_to_controller(self):
        """Send periodic 'keep_alive' message to controller at given interval.

        Schedule repeated delivery  of 'keep_alive' messages to controller. If their is an issue
        the node-controller communication, reset the process and request a new ID.

        """
        if self._reset == 1:
            self._node.node_id = None
            self._reset = 0
            self._node.print_warn(TAG, 'Connection to OpenCache controller restarted')
            self._send_hello_to_controller()
            return
        else:
            threading.Timer(interval=int(self._node.config["keep_alive_interval"]), function=self._send_keep_alive_to_controller, args=()).start()
        data = {"node-id" : self._node.node_id}
        self._call_id += 1
        try:
            response = lib.do_json_rpc_post(_id=self._call_id, method="keep_alive", host=self._node.config["controller_host"], port=int(self._node.config["controller_port"]), _input=data)
            if "error" in response:
                self._reset = 1
        except Exception:
            self._reset = 1

    def send_goodbye_to_controller(self):
        """Send 'goodbye' message to the controller when exiting node."""
        self._call_id += 1
        try:
            data = {"node-id" : self._node.node_id}
            lib.do_json_rpc_post(_id=self._call_id, method="goodbye", host=self._node.config["controller_host"], port=int(self._node.config["controller_port"]), _input=data)
        except Exception:
            pass

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option("--config", dest="config",
        help="location of configuration file to load")
    (options, args) = parser.parse_args()
    _node = Node(options.config)
