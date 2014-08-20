#!/usr/bin/env python2.7

"""opencachecontroller.py: OpenCache Controller - allows a user to control any number of OpenCache nodes."""

import signal
import optparse
import os

import configparser
import opencache.lib.opencachelib as lib
import opencache.controller.state.opencachemongodb as state
import opencache.controller.api.opencachejsonrpc as api
import opencache.controller.request.opencachefloodlight as request_handling
import zmq

TAG = 'controller'

class Controller():

    config = None

    _state = None
    _api = None
    _request_handling = None
    _notification = None

    def __init__(self, config_path):
        """Initialise controller instance.

        Sets up signal handling to deal with interrupts. Loads configuration file, checks validity and creates
        sensible defaults if values missing. Initialises logger to handle output during running. Starts JSON
        server ready to receive commands from clients and nodes. Starts database ready to store state.

        """
        self._setup_signal_handling()
        self._option_check(config_path)
        parser = configparser.ConfigParser(delimiters='=')
        parser.read(config_path)
        self.config = self._create_config_defaults()
        self.config = lib.load_config(self.config, parser)
        self._logger = lib.setup_logger(self.config["log_path"], TAG, self.config["verbosity"])
        self._state = state.State(self, self.config)
        self._request_handling = request_handling.Request(self)
        self._api = api.Api(self, self.config)
        self._notification = Notification(self)
        self._notification.listen()

    def _option_check(self, config_path):
        if config_path == None:
            print ("Please specify a configuration file using '--config'. Exiting.")
            os._exit(3)

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

    def _create_config_defaults(self):
        """Load configuration defaults before loading the user's configuration"""
        config = dict()
        config['controller_host'] = '127.0.0.1'
        config['controller_port'] = '49001'
        config['notification_port'] = '50001'
        config['database_host'] = '127.0.0.1'
        config['database_port'] = '6379'
        config['openflow_host'] = '127.0.0.1'
        config['openflow_port'] = '8080'
        config['log_path'] = '/var/log/opencache/controller'
        config['node_timeout'] = '30'
        config['verbosity'] = '3'
        return config

    def _setup_signal_handling(self):
        """Setup signal handling for SIGQUIT and SIGINT events"""
        signal.signal(signal.SIGINT, self._exit_controller)
        signal.signal(signal.SIGQUIT, self._exit_controller)

    def _exit_controller(self, signal, frame):
        """Quit the OpenCache controller gracefully"""
        self._api.stop()
        self._state.stop()
        self._request_handling.stop()
        self._notification.stop()
        self.print_info(TAG, 'Caught exit signal: exiting OpenCache controller')
        os._exit(0)

    def hello(self, rpc):
        """Add a new node to the database."""
        node_id = self._state.add_node(rpc.host, rpc.port)
        self.print_info(TAG, ("Node added at %s:%s (ID : %s)") %(rpc.host, rpc.port, node_id))
        result = {'node-id':node_id}
        return result

    def keep_alive(self, rpc):
        """Refresh a node timeout in database."""
        return self._state.update_node(rpc.node_id)

    def goodbye(self, rpc):
        """Remove a node.

        Remove all OpenFlow rules involving this node. Rmeove node from the database.

        """
        self.stop(rpc)
        self.print_info(TAG, ("Node exited with ID : %s") %rpc.node_id)
        return self._state.remove_node(rpc.node_id)

    def start(self, rpc):
        """Send start requests to given nodes.

        Handle the three permutations of node descriptions (all, list or single).

        """
        try:
            self._state.remove_expression(rpc.expr)
            if rpc.node_id == '*':
                for node in self._state.list_nodes():
                    self._start_node(rpc.expr, node)
            elif "|" in rpc.node_id:
                for node in rpc.node_id.split("|"):
                    self._start_node(rpc.expr, node)
            else:
                self._start_node(rpc.expr, rpc.node_id)
            return True
        except Exception as e:
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(rpc.expr)}, code='-32603')

    def _start_node(self, expr, node):
        """Lookup node details and send individual node a start request.

        Add OpenFlow rule to redirect traffic to cache instance.

        """
        call_id = self._state.increment_call_id()
        try:
            node = self._state.get_node_details(node)
            self._send_to_node(call_id, "start", node.host, node.port, {'expr' : expr})
            if "|" in expr:
                for expr in expr.split("|"):
                    self._state.add_node_expression(expr, node)
            else:
                self._state.add_node_expression(expr, node)
        except Exception:
            pass

    def stop(self, rpc):
        """"Send stop requests to given nodes.

        Handle the three permutations of node descriptions (all, list or single).

        """
        try:
            if rpc.node_id == '*':
                for node in self._state.list_nodes():
                    self._stop_node(rpc.expr, node)
            elif '|' in rpc.node_id:
                for node in rpc.node_id.split("|"):
                    self._stop_node(rpc.expr, node)
            else:
                self._stop_node(rpc.expr, rpc.node_id)
            return True
        except Exception as e:
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(rpc.expr)}, code='-32603')

    def _stop_node(self, expr, node):
        """Lookup node details and send individual node a stop request.

        Remove OpenFlow rule to redirect traffic to cache instance.

        """
        call_id = self._state.increment_call_id()
        try:
            node = self._state.get_node_details(node)
            if "|" in expr:
                for expr in expr.split("|"):
                    self._state.remove_node_expression(expr, node)
            else:
                self._state.remove_node_expression(expr, node)
            self._send_to_node(call_id, "stop", node.host, node.port, {'expr' : expr})
        except Exception:
            pass

    def pause(self, rpc):
        """Send pause requests to given nodes.

        Handle the three permutations of node descriptions (all, list or single).

        """
        try:
            if rpc.node_id == '*':
                for node in self._state.list_nodes():
                    self._pause_node(rpc.expr, node)
            elif "|" in rpc.node_id:
                for node in rpc.node_id.split("|"):
                    self._pause_node(rpc.expr, node)
            else:
               self._pause_node(rpc.expr, rpc.node_id)
            return True
        except Exception as e:
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(rpc.expr)}, code='-32603')


    def _pause_node(self, expr, node):
        """Lookup node details and send individual node a pause request."""
        call_id = self._state.increment_call_id()
        try:
            node = self._state.get_node_details(node)
            self._send_to_node(call_id, "pause", node.host, node.port, {'expr' : expr})
        except Exception:
            pass

    def stat(self, rpc):
        """Retrieve statistics from the database.

        Handle the three permutations of node descriptions (all, list or single). Do final calculations and conversion
        for the aggregate statistic.

        """
        try:
            total_result = dict([('total_cache_miss', 0), ('total_cache_miss_size', 0), ('total_cache_hit', 0),
                ('total_cache_hit_size', 0), ('total_cache_object', 0), ('total_cache_object_size', 0),
                ('start', 0), ('stop', 0), ('pause', 0), ('total_response_count',0), ('total_node_id_count',0),
                ('total_expr_count',0), ('node_id_seen', set()), ('expr_seen', set()), ('node_expr_pairs_seen', set())])
            if rpc.node_id == '*':
                for node in self._state.list_nodes():
                    total_result = self._stat_node(rpc.expr, node, total_result)
            elif "|" in rpc.node_id:
                for node in rpc.node_id.split("|"):
                    total_result = self._stat_node(rpc.expr, node, total_result)
            else:
                total_result = self._stat_node(rpc.expr, rpc.node_id, total_result)
            total_result['total_node_id_count'] = len(total_result['node_id_seen'])
            total_result['total_expr_count'] = len(total_result['expr_seen'])
            total_result['total_response_count'] = len(total_result['node_expr_pairs_seen'])
            total_result['node_id_seen'] = list(total_result['node_id_seen'])
            total_result['expr_seen'] = list(total_result['expr_seen'])
            total_result['node_expr_pairs_seen'] = list(total_result['node_expr_pairs_seen'])
            return total_result
        except Exception as e:
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(rpc.expr)}, code='-32603')

    def _stat_node(self, expr, node, total_result):
        """Retrieve a cache instance's statistics.

        Add these statistics to an aggregate.

        """
        try:
            if "|" in expr:
                for expr in expr.split("|"):
                    stat = self._state.get_stat(expr, node)
                    total_result = self._add_to_total(stat, total_result)
            else:
                stat = self._state.get_stat(expr, node)
                total_result = self._add_to_total(stat, total_result)
            return total_result
        except Exception:
            pass
        finally:
            return total_result

    def _add_to_total (self, result, total_result):
        """Add an individual cache instances statistics to the aggregate statistic."""
        try:
            total_result['node_id_seen'].add(result.node_id)
            total_result['expr_seen'].add(result.expr)
            total_result['node_expr_pairs_seen'].add((result.node_id, result.expr, result.status, result.avg_load))
            if result.status == 'start':
                total_result['start'] += 1
            elif result.status == 'stop':
                total_result['stop'] += 1
            elif result.status == 'pause':
                total_result['pause'] += 1
            total_result['total_cache_miss'] += int(result.cache_miss)
            total_result['total_cache_miss_size'] += int(result.cache_miss_size)
            total_result['total_cache_hit'] += int(result.cache_hit)
            total_result['total_cache_hit_size'] += int(result.cache_hit_size)
            total_result['total_cache_object'] += int(result.cache_object)
            total_result['total_cache_object_size'] += int(result.cache_object_size)
            return total_result
        except Exception:
            pass
        finally:
            return total_result

    def refresh(self, rpc):
        """Send new stat requests to given nodes to refresh data in controller.

        Handle the three permutations of node descriptions (all, list or single).

        """
        try:
            if rpc.node_id == '*':
                for node in self._state.list_nodes():
                    self._refresh_node(rpc.expr, node)
            elif "|" in rpc.node_id:
                for node in rpc.node_id.split("|"):
                    self._refresh_node(rpc.expr, node)
            else:
               self._refresh_node(rpc.expr, rpc.node_id)
            return True
        except Exception as e:
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(rpc.expr)}, code='-32603')

    def _refresh_node(self, expr, node):
        """Lookup node details and send individual node a stat request."""
        call_id = self._state.increment_call_id()
        try:
            node = self._state.get_node_details(node)
            self._send_to_node(call_id, "stat", node.host, node.port, {'expr' : expr})
        except Exception:
            pass

    def seed(self, rpc):
        """Send seed requests to given nodes.

        Handle the three permutations of node descriptions (all, list or single).

        """
        try:
            if rpc.node_id == '*':
                for node in self._state.list_nodes():
                    self._seed_node(rpc.expr, node)
            elif "|" in rpc.node_id:
                for node in rpc.node_id.split("|"):
                    self._seed_node(rpc.expr, node)
            else:
               self._seed_node(rpc.expr, rpc.node_id)
            return True
        except Exception as e:
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(rpc.expr)}, code='-32603')

    def _seed_node(self, expr, node):
        """Lookup node details and send individual node a seed request."""
        call_id = self._state.increment_call_id()
        try:
            node = self._state.get_node_details(node)
            self._send_to_node(call_id, "seed", node.host, node.port, {'expr' : expr})
        except Exception:
            pass

    def fetch(self, rpc):
        """Send fetch requests to given nodes.

        Handle the three permutations of node descriptions (all, list or single).

        """
        try:
            if rpc.node_id == '*':
                for node in self._state.list_nodes():
                    self._fetch_node(rpc.expr, node)
            elif "|" in rpc.node_id:
                for node in rpc.node_id.split("|"):
                    self._fetch_node(rpc.expr, node)
            else:
               self._fetch_node(rpc.expr, rpc.node_id)
            return True
        except Exception as e:
            raise lib.RemoteProcedureCallError(data={'exception' : str(e), 'node_id' : str(node.node_id), 'expr' : str(rpc.expr)}, code='-32603')


    def _fetch_node(self, expr, node):
        """Lookup node details and send individual node a seed request."""
        call_id = self._state.increment_call_id()
        try:
            node = self._state.get_node_details(node)
            self._send_to_node(call_id, "fetch", node.host, node.port, {'expr' : expr})
        except Exception:
            pass

    def _send_to_node(self, call_id, method, host, port, _input={}):
        """Send request to given node."""
        result = lib.do_json_rpc_post(_id=call_id, method=method, host=host, port=port, _input=_input)
        return result

class Notification():

    _socket = None
    _controller = None
    _context = None

    def __init__(self, controller):
        """Initialise a socket to receive notifications on."""
        self._controller = controller
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.PULL)
        self._socket.bind("tcp://" + controller.config["controller_host"] + ":" + controller.config["notification_port"])

    def stop(self):
        """Stop listening to requests and close the socket."""
        self._socket.close()
        self._context.term()

    def listen(self):
        """Handle notifications from cache instances."""
        while True:
            notification = self._socket.recv_json()
            if notification['method'] == 'redir' and  notification['id'] == None:
                self._handle_redir_message(notification)
            elif notification['method'] == 'stat' and  notification['id'] == None:
                self._handle_stat_message(notification)
            elif notification['method'] == 'alert' and  notification['id'] == None:
                self._handle_alert_message(notification)

    def _handle_redir_message(self, notification):
        """Handle a redirect message. Either add the redirect or remove it, depending on the message."""
        if notification['params']['action'] == 'add':
            try:
                self._controller._request_handling.add_redirect(str(notification['params']['expr']), str(notification['params']['host']),
                    str(notification['params']['port']), str(self._controller.config['openflow_host']), str(self._controller.config['openflow_port']))
            except KeyError:
                self._controller.print_error(TAG, 'Could not add redirect, device attachment point not found.')
        elif notification['params']['action'] == 'remove':
            self._controller._request_handling.remove_redirect(str(notification['params']['expr']), str(notification['params']['host']),
                str(notification['params']['port']), str(self._controller.config['openflow_host']), str(self._controller.config['openflow_port']))

    def _handle_stat_message(self, notification):
        """Handle a stat message. Add this data to the database."""
        self._controller._state.add_stat(notification['params']['expr'], notification['params']['node_id'], notification['params']['status'],
            notification['params']['avg_load'], notification['params']['cache_miss'], notification['params']['cache_miss_size'],
            notification['params']['cache_hit'], notification['params']['cache_hit_size'],  notification['params']['cache_object'],
            notification['params']['cache_object_size'])

    def _handle_alert_message(self, notification):
        """Handle an alert and print warning."""
        if notification['params']['type'] == 'load':
            self._controller.print_warn(TAG, 'Load notification received from node %s with expression %s. Load at: %s requests per second.' % (notification['params']['node_id'], notification['params']['expr'], notification['params']['value']))
        elif notification['params']['type'] == 'disk':
            self._controller.print_warn(TAG, 'Disk notification received from node %s with expression %s. Disk usage at: %s bytes.' % (notification['params']['node_id'], notification['params']['expr'], notification['params']['value']))


if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option("--config", dest="config",
        help="location of configuration file to load")
    (options, args) = parser.parse_args()
    _controller = Controller(options.config)
