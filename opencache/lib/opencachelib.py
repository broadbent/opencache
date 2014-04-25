#!/usr/bin/env python2.7      

"""opencachelib.py: Core OpenCache functionality shared between controller and node."""

import httplib
import json
import os
import shutil
import urllib2
import logging
import logging.handlers

TAG = "lib"

def setup_logger(log_path, name, verbosity):
    """Setup logging functionality to both console and a rotating log file."""
    logger = logging.getLogger('opencache')
    logger.setLevel(logging.DEBUG)
    create_directory(log_path)
    try:
        fh = logging.handlers.RotatingFileHandler(log_path + name + ".log", maxBytes=1073741824)
    except IOError:
        fh = logging.handlers.RotatingFileHandler('node.log', maxBytes=1073741824)
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s][%(levelname)s]%(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.verbosity = verbosity
    return logger

def create_directory(path):
    """Create a new directory if it doesn't exist."""
    while not os.path.isdir(path):
        try:
            os.makedirs(path)
        except Exception:
            raise

def delete_directory(path):
    """Removed an existing directory used for storing cached content specific to this HTTP server's expression."""
    if os.path.isdir(path):
        try:
            shutil.rmtree(path)
        except Exception:
            raise

def expr_split(expr):
    expr_split = expr.split("/", 1)
    root = expr_split[0]
    try:
        path = expr_split[1]
    except Exception:
        path = ''
    return root, path

def log_debug(tag, string):
    """Print a formatted error message if verbosity level permits."""
    logger = logging.getLogger('opencache')
    if int(logger.verbosity) >= 4:
        logger.debug("[" + tag + "] " + string)

def log_info(tag, string):
    """Print a formatted information message if verbosity level permits."""
    logger = logging.getLogger('opencache')
    if int(logger.verbosity) >= 3:
        logger.info("[" + tag + "] " + string)

def log_warn(tag, string):
    """Print a formatted warning message if verbosity level permits."""
    logger = logging.getLogger('opencache')
    if int(logger.verbosity) >= 2:
        logger.warn("[" + tag + "] " + string)

def log_error(tag, string):
    """Print a formatted error message if verbosity level permits."""
    logger = logging.getLogger('opencache')
    if (logger.verbosity) >= 1:
        logger.error("[" + tag + "] " + string)

def load_config(config, parser):
    """Load configuration settings from the configuration file"""
    for name, value in parser.items('config'):
        config[name] = value
    return config

def do_json_rpc_post(_id, method, host, port, _input=None):
    """Format JSON request as JSON-RPC with HTTP POST."""
    if _input==None:
        try:
            post_data = json.dumps({"id":_id, "method":method, "jsonrpc":"2.0"})
            return do_json_post(host=host, port=port, post_data=post_data)
        except Exception as exception:
            log_error(TAG,  "Could not encode JSON: %s" % exception)
    else:
        try:
            post_data = json.dumps({"id":_id, "method":method, "params":_input, "jsonrpc":"2.0"})
            return do_json_post(host=host, port=port, post_data=post_data)
        except Exception as exception:
            log_error(TAG,  "Could not encode JSON: %s" % exception)

def do_json_rest_post(host, port, _json, path):
    """Format JSON request as REST with HTTP POST."""
    try:
        return do_json_post(host=host, port=port, post_data=_json, path=path)
    except Exception as exception:
        log_error(TAG,  "Could not encode JSON: %s" % exception)

def do_json_rest_delete(host, port, _json, path):
    """Format JSON request as REST with HTTP DELETE."""
    conn = httplib.HTTPConnection(host + ':' + port)
    conn.request('DELETE', path, _json) 
    resp = conn.getresponse()
    content = resp.read()
    return content

def do_json_post(host, port, post_data, path=None):
    """Make a JSON call to given destination."""
    httplib.HTTPConnection._http_vsn = 10
    httplib.HTTPConnection._http_vsn_str = 'HTTP/1.0'
    if path == None:
        url =  "http://%s:%s" % (host, port)
        try:
            response_data = urllib2.urlopen(url, post_data, 30).read()
            try:
                response_json = json.loads(response_data)
                return response_json
            except Exception as exception:
                log_error(TAG,  "Could not decode JSON from response: %s" % exception)
        except Exception as exception:
            log_error(TAG,  "Could not connect to %s:%s: %s" % (host, port, exception))
            raise
    else:
        url =  "http://%s:%s%s" % (host, port, path)
        try:
            response_data = urllib2.urlopen(url, post_data, 30).read() 
            try:
                response_json = json.loads(response_data)
                return response_json
            except Exception as exception:
                log_error(TAG,  "Could not decode JSON from response: %s" % exception)
        except IOError as exception:
            log_error(TAG,  "Could not connect: %s" % exception)
            raise

def send_json_rpc_result(JSONHandler, request_id, result):
    """Send JSON result message in response to successful call."""
    JSONHandler.send_response(200)
    JSONHandler.send_header("Content-type", 'application/json')
    JSONHandler.end_headers()
    try:
        message = json.dumps({"id":request_id, "result":result, "jsonrpc":"2.0"})
    except Exception as exception:
        log_error(TAG,  "Could not encode JSON: %s" % exception)
    JSONHandler.wfile.flush()
    JSONHandler.wfile.write(message + '\n\r\n') 
    JSONHandler.wfile.flush()
    JSONHandler.wfile.close()
    return

def send_json_rpc_error(JSONHandler, request_id, code, data=None):
    """Send JSON error message in response to failed call."""
    error = {}
    error["code"] = code
    if code == '-32700':
        error["message"] = 'Parse error'
    elif code == '-32600':
        error["message"] = 'Invalid Request'
    elif code == '-32601':
        error["message"] = 'Method not found'
    elif code == '-32602':
        error["message"] = 'Invalid params'
    elif code == '-32603':
        error["message"] = 'Internal error'
    JSONHandler.send_response(200)
    JSONHandler.end_headers()
    if data != None:
        error["data"] = str(data)
    message = json.dumps({"id":request_id, "error":error, "jsonrpc":"2.0"})
    JSONHandler.wfile.write(message)
    JSONHandler.wfile.close()

class RemoteProcedureCallError(Exception):
    def __init__(self, data, code):
        self.data = data
        self.code = code

    def __str__(self):
        return repr(self.data)