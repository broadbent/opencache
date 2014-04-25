# OpenCache #

OpenCache is an experimental HTTP caching platform that utilises [OpenFlow-enabled](https://www.opennetworking.org/sdn-resources/onf-specifications/openflow) switches to provide transparent content delivery. It works in a controller-node architecture, described in the [Architecture](https://github.com/broadbent/opencache#architecture) section. 

Progress is quickly advancing, with a number of features to be implemented shortly (see [TODO](https://github.com/broadbent/opencache/TODO.md) for more details).

## Requirements ##

OpenCache is written for Python 2.7 and is tested on Unix platforms. It is recommended that `pip` is used to automatically install OpenCache and any additional dependencies. 

The OpenCache controller uses the [pymongo](https://pypi.python.org/pypi/pymongo/) library to interact with a [MongoDB](http://www.mongodb.org/) database. [pyzmq](https://github.com/zeromq/pyzmq) is required for internal ØMQ messaging. Backported from Python 3.2+ to Python 2.6-2.7, [configparser](https://pypi.python.org/pypi/configparser) is also used for allowing additional flexibility in configuration files.

## Installation ##

### pip ###

To install or upgrade pip, download [get-pip.py](https://raw.github.com/pypa/pip/master/contrib/get-pip.py).

Then run the following (which may require administrator access):

```bash
$ python get-pip.py
```

For more detailed instructions and alternative installation methods, please visit the [pip](http://www.pip-installer.org/en/latest/installing.html) website.

### opencache ###

OpenCache can be installed easily using `pip` and [PyPi](https://pypi.python.org/pypi):

```bash
$ pip install opencache --pre
```

As OpenCache is still in a pre-release phase, it is necessary to use the `--pre` flag at the moment (to retrieve _any_ release).

Alternatively, `distutils` can be used to install OpenCache from source. Simply download the compressed repository, uncompress, and run:

```bash
$ python setup.py install
```

## Running OpenCache ##

OpenCache is split into two parts: the controller and the node. See the [Architecture](https://github.com/broadbent/opencache/README.md#architecture) section for more details. 

To run the OpenCache controller, simply use:
```bash
$ opencache --controller --config="PATH_TO_CONFIG"
```

Similarly, to run the OpenCache node, use:
```bash
$ opencache --node --config="PATH_TO_CONFIG"
```

Sample configuration files are included in `example\config` directory for both a controller and a node (see `controller.conf` and `node.conf` respectively). Runtime output is written to both a log file and to `stdout`. The destination file for this log can be specified in the  configuration file.

## Updating ##

If you are using the OpenCache [PyPi](https://pypi.python.org/pypi) distribution, simply run `--upgrade` to update to the latest version:

```bash
$ pip install opencache --pre --upgrade
```

## Architecture ##

OpenCache operates in a controller-node architecture. This means that each node is configured to connect to a single controller. This controller is then responsible for the behaviour of any nodes that connect to it. This creates a centralised point of control. A user (or application) can interact with an OpenCache deployment through this controller by using the [JSON-RPC Interface](https://github.com/broadbent/opencache/README.md#json-rpc-interface).

The controller maintains the state of connected nodes. If a controller does not receive a message from a controller within a pre-determined time limit, the controller assumes the node is disconnected. Each node will maintain connectivity with the controller using periodic `keep_alive` messages.

## JSON-RPC Interface ##

To interface with OpenCache, a standard [JSON-RPC](http://www.jsonrpc.org/specification#error_object) can be made to the controller. All requests must be sent via the HTTP `POST` method.

The following RPCs are used to interact with a an OpenCache deployment via a controller (more details for each method given below):

| method                  | params                                          | result                            |
|-------------------------|-------------------------------------------------|-----------------------------------|
| `start`                 | `{ ("expr" : <expr>), ("node" : <node>) }`   	| `<boolean>`                       |
| `stop`                  | `{ ("expr" : <expr>), ("node" : <node>) }`   	| `<boolean>`                       |
| `pause`                 | `{ ("expr" : <expr>), ("node" : <node>) }`   	| `<boolean>`                       |
| `fetch`                 | `{ ("expr" : <expr>), ("node" : <node>) }`  	| `<boolean>`                       |
| `seed`                  | `{ ("expr" : <expr>), ("node" : <node>) }`  	| `<boolean>`                       |
| `refresh`               | `{ ("expr" : <expr>), ("node" : <node>) }`  	| `<boolean>`                       |
| `stat`                  | `{ ("expr" : <expr>), ("node" : <node>) }`  	| `[<cache_hit>, <cache_miss>... ]` |


Parameters in brackets are optional. If not included, a wildcard all (`*`) is used. A `<node>` can be either a single node, a vertical-bar-seperated (`|`) list of nodes or a wildcard (`*`) for all existing nodes. An `<expr>` can either be a single OpenCache expression, a vertical-bar-seperated (`|`) list of OpenCache expressions or a wildcard (`*`) to cache all HTTP traffic.

### start ###

Start the given cache instances. Creates new instances if they do not exist, and restarts those that are paused.

*Return Value:* Returns a `true` result message on success or an error message on failure.

### stop ###

Stop the given cache instances. Prevents them from responding to requests and terminates the running instance. Content is removed from disk.

*Return Value:* Returns a `true` result message on success or an error message on failure.

### pause ###

Pause the given cache instances, temporarily stopping request handing but _not_ removing content from disk. Restart again using `start` command.

*Return Value:* Returns a `true` result message on success or an error message on failure.

### fetch ###

Fetch and retrieve an object from a remote location. Considered as 'pre-caching' content on the node, ready to serve subsequent requests. Similar to a 'cache-miss' event, where content is not present in the cache and must be retrieved.

*Return Value:* Returns a `true` result message on success or an error message on failure.

### seed ###

Artifically add a number of fully resolved expressions to the given nodes. Each one of these expressions is seen as equivalent to each other, and will serve the same content given a request. For example, this feature can be used to define a single object, stored in multiple locations; with the use of `seed`, the object will only be stored once in each node, reducing storage utilisation.

*Return Value:* Returns a `true` result message on success or an error message on failure.

### refresh ###

Manually request fresh statistics from given cache instances. Does not rely on periodic reporting. Useful if you want the most up to date statistics.

*Return Value:* Returns a `true` result message on success or an error message on failure.

### stat ###

Return aggregate statistics for  given cache instances. These stats are stored at the controller to reduce latency. Cache instances will periodically report stats back to the controller. To manually request fresh statistics from given cache instances, use the `refresh` command before this (it may also be necessary to insert a delay to ensure fresh statistics are received back to the controller from all cache instances). Stats are kept for a predefined period of time that is configurable.

*Return Value:*

| field                     | note                                                                                      	|
|---------------------------|-----------------------------------------------------------------------------------------------|
| `start`                   | number of cache instances in 'start' state.                                               	|
| `stop`                    | number of cache instances in 'stop' state.                                                	|
| `pause`                   | number of cache instances in 'paused' state.                                              	|
| `cache_miss`              | number of cache miss (content not found in cache) events (one per request).               	|
| `cache_miss_size`         | number of bytes served whilst handling cache miss (content not found in cache) events.    	|
| `cache_hit`               | number of cache hit (content already found in cache) events (one per request).            	|
| `cache_hit_size`          | number of bytes served whilst handling cache hit (content already found in cache) events. 	|
| `cache_object`            | number of objects currently stored by the cache.                                          	|
| `cache_object_size`       | number of bytes for the cached objects on disk (actual).                                  	|
| `total_node_count`     	| number of unique node IDs present in results                                              	|
| `total_expr_count`        | number of unique expressions present in results                                           	|
| `total_response_count`    | number of unique responses seen                                                           	|
| `node_seen`            	| list of those node IDs present in results                                                 	|
| `expr_seen`               | list of those expressions present in results                                              	|
| `node_expr_pairs_seen`    | pairs of nodes and expressions present in results, including current status and average load	|

## Performance ##

OpenCache should be considered an experimental prototype, and is not built for production environments.

However, this is not to say that OpenCache performs poorly, rather it is not optimised for performance yet.

Currently, a cache instance is single-process but multi-threaded. Running alone on an 2.5GHz i5, one such instance can handle a maximum of ~650 requests per second (based on initial testing).

## License ##

This sofware is licensed under the [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).

## Releases ##

OpenCache follows the [Semantic Versioning System](http://semver.org/spec/v2.0.0.html) for numbering releases.

## Author ##

OpenCache is developed and maintained by Matthew Broadbent (matt@matthewbroadbent.net). It can be found on GitHub at: http://github.com/broadbent/opencache.
