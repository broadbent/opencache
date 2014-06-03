#!/usr/bin/env python2.7

"""opencachemongodb.py - Manages the state of the node contents using a MongoDB database."""

import time

import pymongo

TAG = 'state'

class State:

    def __init__(self, node):
        """Initialise state instance with useful objects.

        Instantiated controller and configuration objects are passed for use within this instance.
        Try connecting to the database. Continue to do so until database information is returned
        (and the connection is therefore successful).

        """
        self._node = node
        database_test = None
        while (database_test == None):
            try:
                self._client = pymongo.MongoClient(self._node.config['database_host'], int(self._node.config['database_port']))
                self._database = self._client[self._node.config['database_name']]
                database_test = self._database.command("serverStatus")
            except Exception as e:
                self._node.print_warn(TAG, "Could not connect to MongoDB database, retrying in 15 seconds.")
                time.sleep(15)

    def create(self, document):
        return self._database.content.insert(document, upsert=True)

    def remove(self, document):
        return self._database.content.remove(document)

    def lookup(self, document):
        result = self._database.content.find(document)
        result_obj = []
        for test in result:
            result_obj.append(test)
        return result_obj
