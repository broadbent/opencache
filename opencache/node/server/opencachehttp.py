#!/usr/bin/env python2.7

"""opencachehttp.py: HTTP Server - serves cached HTTP objects to requesting clients."""

import BaseHTTPServer
import collections
import hashlib
import httplib
import os
import signal
import SocketServer
import sys
import threading

import opencache.lib.opencachelib as lib
import opencache.node.state.opencachemongodb as database
import zmq

TAG = 'server'

class Server:

    _server_path = None
    _server = None
    _port = None
    _ipc_socket = None
    _context = None
    _node = None
    _expr = None
    _load = 0
    _load_data = None

    def __init__(self, node, expr, port):
        """Initialise server instance.

        Creates new connection manager. Creates new HTTP server. Passes objects to the server to facilitate
        callbacks. Sets server status to 'start'. Runs server until terminated.

        """
        self._setup_signal_handling()
        self._database = node.database
        self._node = node
        self._expr = expr
        self._port = port
        self._load_data = collections.deque(maxlen=int(self._node.config["stat_refresh"]))
        self._set_path(expr)
        lib.create_directory(self._server_path)
        self._server = self.ThreadedHTTPServer(('', self._port), self.HandlerClass)
        #self._server = self.ThreadedHTTPServer((self._node.config["node_host"], self._port), self.HandlerClass)
        self._server._setup_signal_handling()
        self._server._server = self
        self._server._node = self._node
        self._server._expr = self._expr
        self._server._server_path = self._server_path
        threading.Thread(target=self._conn_manager, args=(expr, )).start()
        threading.Thread(target=self._load_monitor, args=()).start()
        threading.Thread(target=self._stat_reporter, args=()).start()
        self._start()
        self._server.serve_forever()


    def _setup_signal_handling(self):
        """Setup signal handling for SIGQUIT and SIGINT events"""
        signal.signal(signal.SIGINT, self._exit_server)
        signal.signal(signal.SIGQUIT, self._exit_server)

    def _exit_server(self, signal, frame):
        raise SystemExit

    def _conn_manager(self, expr):
        """Manage inter-process communication (IPC) connections.

        Receives messages from the OpenCache node process, instructing it call start/stop/pause/stat methods.

        """
        self._context = zmq.Context()
        self._ipc_socket = self._context.socket(zmq.SUB)
        self._ipc_socket.connect("ipc://oc")
        self._ipc_socket.setsockopt_string(zmq.SUBSCRIBE, expr.decode('ascii'))
        while True:
            string = self._ipc_socket.recv_string()
            expr, call, path, transaction = string.split()
            if transaction == '?' or path == '?':
                getattr(self, "_" + str(call))()
            else:
                getattr(self, "_" + str(call))(path, transaction)

    def _send_message_to_controller(self, message):
        """Send given message to controller notification port."""
        context = zmq.Context()
        ipc_socket = context.socket(zmq.PUSH)
        ipc_socket.connect("tcp://" +  self._node.config["controller_host"] + ":" + self._node.config["notification_port"])
        ipc_socket.send_json(message)

    def _stat_reporter(self):
        """Report statistics back to the controller periodcially."""
        threading.Timer(interval=int(self._node.config["stat_refresh"]), function=self._stat_reporter, args=()).start()
        self._stat()

    def _load_monitor(self):
        """Monitor the request load every second. Send alert to controller if it exceeds a configured amount."""
        threading.Timer(interval=int(1), function=self._load_monitor, args=()).start()
        self._current_load = self._server._load
        self._load_data.append(self._current_load)
        self._server._load = 0
        if int(self._current_load) > int(self._node.config["alert_load"]):
            self._send_message_to_controller(self._get_alert('load', self._current_load))

    def _get_average_load(self):
        """Calculate load average over given time."""
        average = 0
        for data_point in self._load_data:
            average += int(data_point)
        average = average/int(self._node.config["stat_refresh"])
        return average

    def _get_alert(self, alert_type, value):
        """Get message body for an alert notification to the controller."""
        alert = dict()
        alert['method'] = 'alert'
        alert['id'] = None
        alert['params'] = dict()
        alert['params']['expr'] = self._server._expr
        alert['params']['node_id'] = self._node.node_id
        alert['params']['type'] = alert_type
        alert['params']['value'] = value
        return alert

    def _start(self):
        """Start the HTTP server.

        Create directory for cached content to be stored and allow HTTP server to start receiving requests.
        Set status to indicate new state.

        """
        self._server._stop = False
        self._server._status = 'start'
        self._send_message_to_controller(self._get_redirect('add'))

    def _stop(self):
        """Stop the HTTP server.

        Stop HTTP server from receiving requests and remove directory used to store cached content.
        Set status to indicate new state.

        """
        self._send_message_to_controller(self._get_redirect('remove'))
        self._server._stop = True
        self._database.remove({'expr' : self._expr})
        lib.delete_directory(self._server_path)
        self._server._status = 'stop'
        self._stat()

    def _pause(self):
        """Pause the HTTP server.

        Pause HTTP server, temporarily preventing the receipt of requests. Set status to indicate new state.

        """
        self._send_message_to_controller(self._get_redirect('remove'))
        self._server._stop = True
        self._server._status = 'pause'

    def _get_redirect(self, action):
        """Get message body for a redirect notification to the controller."""
        redirect = dict()
        redirect['method'] = 'redir'
        redirect['id'] = None
        redirect['params'] = dict()
        redirect['params']['expr'] = self._server._expr
        redirect['params']['node_id'] = self._node.node_id
        redirect['params']['host'] = self._node.config['node_host']
        redirect['params']['port'] = self._port
        redirect['params']['action'] = action
        return redirect

    def _stat(self):
        """Retrieve statistics for this HTTP server and send them to the controller."""
        self._send_message_to_controller(self._get_stats())

    def _get_stats(self):
        """Get message body for a statistics notification to the controller.

        The statistics returned to the controller include:

        status -- current status of the HTTP server
        expr -- the OpenCache expression to which this node is serving
        node_id -- the ID number given to the node by the OpenCache controller
        cache_miss -- number of cache miss (content not found in cache) events (one per request)
        cache_miss_size -- number of bytes served whilst handling cache miss (content not found in cache) events
        cache_hit -- number of cache hit (content already found in cache) events (one per request)
        cache_hit_size -- number of bytes served whilst handling cache hit (content already found in cache) events
        cache_object -- number of objects currently stored by the cache
        cache_object_size -- size of cached objects on disk (actual, in bytes)

        """
        statistics = dict()
        statistics['method'] = 'stat'
        statistics['id'] = None
        statistics['params'] = dict()
        statistics['params']['status'] = self._server._status
        statistics['params']['avg_load'] = self._get_average_load()
        statistics['params']['expr'] = self._server._expr
        statistics['params']['node_id'] = self._node.node_id
        statistics['params']['cache_miss'] = self._server._cache_miss
        statistics['params']['cache_miss_size'] = self._server._cache_miss_size
        statistics['params']['cache_hit'] = self._server._cache_hit
        statistics['params']['cache_hit_size'] = self._server._cache_hit_size
        statistics['params']['cache_object'] = len(self._database.lookup({}))
        dir_size = get_dir_size(self._server_path)
        statistics['params']['cache_object_size'] = dir_size
        return statistics

    def _set_path(self, expr):
        """Set the path used to store cached content specific to this HTTP server's expression."""
        self._server_path = self._node.config["cache_path"] + hashlib.sha224(expr).hexdigest()

    class ThreadedHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
        """Create a threaded HTTP server."""
        allow_reuse_address = True
        daemon_threads = True
        _stop = True
        _status = 'start'
        _cache_hit_size = 0
        _cache_miss_size = 0
        _cache_hit = 0
        _cache_miss = 0
        _load = 0
        _status = None
        _node = None
        _server_path = None
        _expr = None
        _server = None

        def _setup_signal_handling(self):
            """Setup signal handling for SIGQUIT and SIGINT events"""
            signal.signal(signal.SIGINT, self._exit_server)
            signal.signal(signal.SIGQUIT, self._exit_server)

        def _exit_server(self, signal, frame):
            raise SystemExit

        def serve_forever (self):
            """Overide default behaviour to handle one request at a time until state is changed.

            Serve content as long as the HTTP server is a 'start' state. When 'paused' or 'stopped',
            requests will not be handled.

            """
            while True:
                if self._stop != True:
                    print 'handle'
                    self.handle_request()
                    self._load += 1

    class HandlerClass(BaseHTTPServer.BaseHTTPRequestHandler):

        def log_message( self, format, *args ):
            """Ignore log messages."""
            pass

        def do_GET(self):
            """Handle incoming GET messages from clients.

            Calculate hash value for content request. Check to see if this has already been cached.
            If it has, a cache hit occurs. If the content is not present on the disk or has not
            been cached previously, a cache miss occurs.

            """
            key = hashlib.sha224(self.path).hexdigest()
            if len(self.server._server._database.lookup({'key' : key})) == 1:
                try:
                    self._cache_hit(key)
                except (IOError, OSError) as e:
                    self.server._node.print_warn(TAG, ('Could not retrieve content from filesystem, cache miss\'ing instead: %s' % e))
                    self._cache_miss(key)
            else:
                self._cache_miss(key)

        def do_POST(self):
            """Ignore POST messages."""
            pass

        def _cache_hit(self, key):
            """The content has been seen before, and should be sent to the client using the cached copy.

            Statistics updated accordingly.

            """

            path = self.server._server._database.lookup({'key' : key})[0]['path']
            try:
                self.server._node.print_debug(TAG, 'cache hit: %s%s' %(self.server._expr, self.path))
                f = open(path, 'r')
                local_object = f.read()
                self._send_object(local_object)
                f.close()
                self.server._cache_hit += 1
                self.server._cache_hit_size += sys.getsizeof(local_object)
            except IOError:
                raise

        def _cache_miss(self, key):
            """The content has not been seen before, and needs to be retrieved before it can be
             sent to the client.

            Once the content has been delivered, the object can be stored on disk to serve future
            cache requests. Statistics updated accordingly.

            """
            try:
                self.server._node.print_debug(TAG, 'cache miss: %s%s' %(self.server._expr, self.path))
                remote_object = self._fetch_and_send_object(self.server._expr)
                if self._disk_check():
                    lookup = self.server._server._database.lookup({'key' : key})
                    if len(lookup) == 1:
                        object_path = lookup[0]['path']
                    else:
                        object_path = self.server._server_path + "/" + key
                    f = open(object_path, 'w')
                    f.write(remote_object)
                    f.close()
                    self.server._server._database.create({'expr' : self.server._expr, 'key' : key, 'path' : object_path})
                else:
                    self.server._node.print_info(TAG, 'Cache instance has reached maximum disk usage and cannot store object: %s%s' %(self.server._expr, self.path))
                self.server._cache_miss += 1
                self.server._cache_miss_size += sys.getsizeof(remote_object)
            except Exception as e:
                pass

        def _disk_check(self):
            """Check if it possible to write a given object to disk.

            If the current directory size is greater than the 'alert_disk' configuration setting, send an alert to the controller.

            """
            dir_size = get_dir_size(self.server._server_path)
            if int(dir_size) > int(self.server._node.config["alert_disk"]):
                self.server._server._send_message_to_controller(self.server._server._get_alert('disk', dir_size))
                if int(dir_size) > int(self.server._node.config["max_disk"]):
                    return False
            return True

        def _fetch_and_send_object(self, url):
            """Fetch the object from the original external location and deliver this to the client. """
            connection = httplib.HTTPConnection(url)
            connection.request("GET", self.path)
            response = connection.getresponse()
            length = int(response.getheader('content-length'))
            self.send_response(200)
            self.send_header('Content-type','text-html')
            self.end_headers()
            total_payload = ""
            bytes_read = 0
            while True:
                try:
                    read_payload = response.read(1448)
                except Exception as e:
                    self.server._node.print_error(TAG, 'Could not retrieve content from origin server: %s', e)
                    break
                try:
                    self.wfile.write(read_payload)
                except Exception as e:
                    self.server._node.print_error(TAG, 'Could not deliver fetched content to client: %s', e)
                    break
                total_payload += read_payload
                bytes_read += 1448
                if bytes_read > length:
                    break
            self.wfile.close()
            connection.close()
            self.server._node.print_debug(TAG, 'cache fetched: %s%s at approx. %s bytes' %(url, self.path, bytes_read))
            return total_payload

        def _send_object(self, data):
            """Deliver the cached object to the client"""
            self.send_response(200)
            self.send_header('Content-type','text-html')
            self.end_headers()
            try:
                self.wfile.write(data)
            except Exception as e:
                self.server._node.print_error(TAG, 'Could not deliver cached content to client: %s', e)
            return

def get_dir_size(path):
    """Get size of files (actual, in bytes) for given path"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size
