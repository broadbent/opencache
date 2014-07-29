#!/usr/bin/env python2.7

"""opencachemongodb.py - Manages the state of the controller using a MongoDB database."""

import time
import datetime

import pymongo

TAG = 'state'

class State:

    class _Node():
        """Object representing node details."""

        def __init__(self):
            """Initialise node with sensible default details."""
            self.host = None
            self.port = None

    class _Stat():

        def __init__(self):
            self.expr = None
            self.node_id = None
            self.status = None
            self.cache_miss = None
            self.cache_miss_size = None
            self.cache_hit = None
            self.cache_hit_size = None
            self.cache_object = None
            self.cache_object_size = None

    _client = None
    _database = None
    _nodes = None
    _stats = None
    _counters = None
    _config = None
    _controller = None

    def __init__(self, controller, config):
        """Initialise state instance with useful objects.

        Instantiated controller and configuration objects are passed for use within this instance.
        Try connecting to the database. Continue to do so until database information is returned
        (and the connection is therefore successful).

        """
        self._controller = controller
        self._config = config
        database_test = None
        while (database_test == None):
            try:
                self._client = pymongo.MongoClient(config['database_host'], int(config['database_port']))
                self._database = self._client.opencache
                database_test = self._database.command("serverStatus")
            except Exception as e:
                self._controller.print_warn(TAG, "Could not connect to MongoDB database, retrying in 15 seconds.")
                time.sleep(15)
        self._database.nodes.ensure_index( 'seen', expireAfterSeconds=int(config['node_timeout']))
        self._database.stats.ensure_index( 'seen', expireAfterSeconds=int(config['node_timeout']))

    def stop(self):
        """Stop state object."""
        pass

    def _clear(self):
        """Completely clear entire database."""
        self._database.command("dropDatabase")
        return True

    def increment_call_id(self):
        """Increment call ID number, and return next available."""
        return self._database.counters.find_and_modify( query={ 'name' : 'call_id' },  update={ '$inc' : { 'count': 1 } }, upsert=True, multi=False, new=True)['count']

    def increment_node_id(self):
        return self._database.counters.find_and_modify( query={ 'name' : 'node_id' },  update={ '$inc' : { 'count': 1 } }, upsert=True, multi=False, new=True)['count']

    def add_node(self, host, port):
        """Add a new node to the controller.

        Add a new node to the controller with the given details (hostname and port numbers). Set timeout according
        to configuration. Return new node ID.

        """
        node_id = self.increment_node_id()
        node = {'node_id' : int(node_id), 'host' : host, 'port' : port, 'seen' : datetime.datetime.utcnow()}
        self._database.nodes.insert(node, upset=True)
        return node_id

    def update_node(self, node_id):
        """Update a node in the controller.

        Refresh timeout on for given node ID. Increment the number of times the controller has seen this node.
        If the node has not been seen before, reset the node (which will generate a new 'hello' message).

        """
        result = self._database.nodes.find_and_modify(query={'node_id' : int(node_id)}, update={ '$set' : {'seen' : datetime.datetime.utcnow()}}, upsert=False, multi=False)
        if result == None:
            self.remove_node(node_id)
            self._controller.print_warn(TAG, ("Node not found (ID : %s)") %(node_id))
        else:
            self._controller.print_info(TAG, ("Node updated (ID : %s)") %(node_id))
            return True

    def remove_node(self, node_id):
        """Remove a node from the controller."""
        self._database.nodes.remove(query={'node_id' : int(node_id)})
        return True

    def list_nodes(self):
        """List all nodes currently connected to the controller (or not timed out yet)."""
        nodes = self._database.nodes.find()
        nodes_list =list()
        for node in list(nodes):
            nodes_list.append(int(node['node_id']))
        return nodes_list

    def get_node_details(self, node_id):
        """Given a node's ID, return it's hostname and port number."""
        result = self._database.nodes.find_one( { 'node_id' : int(node_id) } )
        try:
            node = self._Node()
            node.host = result['host']
            node.port = int(result['port'])
            return node
        except Exception:
            return None

    def add_expression(self, expr):
        """Find nodes that currently have given expression."""
        return self._database.exprs.find_one( {'expr' : expr})['nodes']

    def remove_expression(self, expr):
        """Completely remove an expression from the controller."""
        self._database.exprs.remove({'expr' : expr})
        return True

    def add_node_expression(self, expr, node_id):
        """Add a given node to a given expression."""
        self._database.exprs.update({'expr' : expr}, { '$push' : {'nodes' : int(node_id)}}, upsert=True, multi=False)
        return True

    def remove_node_expression(self, expr, node_id):
        """Remove a given node from a given expression."""
        try:
            self._database.exprs.update({'expr' : expr}, { '$pull' : {'nodes' : int(node_id)}}, upsert=False, multi=False)
            return True
        except Exception:
            pass

    def add_stat(self, expr, node_id, status, avg_load, cache_miss, cache_miss_size, cache_hit, cache_hit_size, cache_object, cache_object_size):
        """Add a stat response to the database.

        Also, update a node as we have seen a periodic response from it.

        """
        self._database.statistics.update({'node_id' : int(node_id), 'expr' : expr}, { '$set' : {'status': status, 'avg_load' : avg_load,
            'cache_miss' : cache_miss, 'cache_miss_size' : cache_miss_size, 'cache_hit' : cache_hit, 'cache_hit_size' : cache_hit_size,
            'cache_object' : cache_object, 'cache_object_size' : cache_object_size, 'seen' : datetime.datetime.utcnow()}}, upsert=True, multi=False)
        self.update_node(node_id)

    def get_stat(self, expr, node_id):
        """Get the stats relating to a specific cache instance."""
        try:
            stat = self._Stat()
            stat.expr = expr
            stat.node_id = node_id
            search_fields = {}
            if not expr == '*':
                search_fields['expr'] = expr
            if not node_id == '*':
                search_fields['node_id'] = int(node_id)
            result = self._database.statistics.find_one(search_fields )
            stat.status = result['status']
            stat.avg_load = result['avg_load']
            stat.cache_miss = result['cache_miss']
            stat.cache_miss_size = result['cache_miss_size']
            stat.cache_hit = result['cache_hit']
            stat.cache_hit_size = result['cache_hit_size']
            stat.cache_object = result['cache_object']
            stat.cache_object_size = result['cache_object_size']
            return stat
        except Exception:
            return None
