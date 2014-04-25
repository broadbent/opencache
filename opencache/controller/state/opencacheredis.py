#!/usr/bin/env python2.7

"""opencacheredis.py - Manages the state of the controller using a Redis database."""

import time

import redis

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

    _database = None
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
            self._database = redis.StrictRedis(config['database_host'], int(config['database_port']), db=0)
            try:
                database_test = self._database.info()
            except Exception:
                self._controller.print_warn(TAG, "Could not connect to redis database, retrying in 15 seconds.")
                time.sleep(15)
                
    def stop(self):
        """Stop state object."""
        pass

    def _clear(self):
        """Completely clear entire database."""
        self._database.flushall()
        return True

    def increment_call_id(self):
        """Increment call ID number, and return next available."""
        return self._database.incr('call_id')

    def add_node(self, host, port):
        """Add a new node to the controller.

        Add a new node to the controller with the given details (hostname and port numbers). Set timeout according 
        to configuration. Return new node ID.

        """
        node_id = self._database.incr('node_id')
        pipe = self._database.pipeline()
        pipe.rpush('node:' + str(node_id), str(host), str(port), 0)
        pipe.expire('node:' + str(node_id), self._config['node_timeout'])
        pipe.execute()
        return node_id

    def update_node(self, node_id):
        """Update a node in the controller.

        Refresh timeout on for given node ID. Increment the number of times the controller has seen this node.
        If the node has not been seen before, reset the node (which will generate a new 'hello' message).

        """
        seen = self._database.lindex('node:' + str(node_id), 2)
        pipe = self._database.pipeline()
        pipe.lset('node:' + str(node_id), 2, seen)
        pipe.expire('node:' + str(node_id), self._config['node_timeout'])
        try:
            pipe.execute()
            self._controller.print_info(TAG, ("Node updated (ID : %s)") %(node_id))
            return True
        except redis.ResponseError:
            self._controller.print_warn(TAG, ("Node not found (ID : %s)") %(node_id))
            self._database.delete('node:' + str(node_id))
            return False

    def remove_node(self, node_id):
        """Remove a node from the controller."""
        self._database.delete('node:' + str(node_id))
        return True

    def list_nodes(self):
        """List all nodes currently connected to the controller (or not timed out yet)."""
        nodes = self._database.keys('node:*')
        return nodes

    def get_node_details(self, node_id):
        """Given a node's ID, return it's hostname and port number."""
        try:
            node = self._Node()
            node.host = self._database.lindex(node_id, 0)
            node.port = int(self._database.lindex(node_id, 1))
            return node
        except Exception:
            return None

    def add_expression(self, expr):
        """Find nodes that currently have given expression."""
        return self._database.lrange(expr, 0, -1)

    def remove_expression(self, expr):
        """Completely remove an expression from the controller."""
        return self._database.delete(expr)


    def add_node_expression(self, expr, node_id):
        """Add a given node to a given expression."""
        return self._database.lpush(expr, node_id)

    def remove_node_expression(self, expr, node_id):
        """Remove a given node from a given expression."""
        try:
            return self._database.lrem(expr, node_id, 0)
        except Exception: 
            pass

    def add_stat(self, expr, node_id, status, avg_load, cache_miss, cache_miss_size, cache_hit, cache_hit_size, cache_object, cache_object_size):
        """Add a stat response to the database. 

        Also, update a node as we have seen a periodic response from it.

        """
        pipe = self._database.pipeline()
        try:
            key = 'stat:' + str(expr) + ':node:' + str(node_id)
            self._database.delete(key)
            pipe.rpush(key, str(status), str(avg_load), str(cache_miss), str(cache_miss_size), str(cache_hit), str(cache_hit_size), 
                str(cache_object), str(cache_object_size))
            pipe.expire(key, self._config['node_timeout'])
            pipe.execute()
        except Exception:
            return None
        self.update_node(node_id)

    def get_stat(self, expr, node_id):
        """Get the stats relating to a specific cache instance."""
        try:
            key = 'stat:' + str(expr) + ':' + str(node_id)
            stat = self._Stat()
            stat.expr = expr
            stat.node_id = node_id.replace('node:', '');
            result = self._database.lrange(key, 0, -1)          
            stat.status = result[0]
            stat.avg_load = result[1]
            stat.cache_miss = result[2]
            stat.cache_miss_size = result[3]
            stat.cache_hit = result[4]
            stat.cache_hit_size = result[5]
            stat.cache_object = result[6]
            stat.cache_object_size = result[7]
            return stat
        except Exception:
            return None
