from flask import Flask, render_template, request
import random
import json
import urllib

app = Flask(__name__)

# class Controller():
#     pass

# class Node():
#     pass


# def index():
#     controller = Controller()
#     node = Node()
#     node.byte = 10000000
#     controller.ip = '192.168.0.1'
#     return render_template('index.html', controller=controller, node=node)

@app.route('/')
@app.route('/management')
@app.route('/management/<mode>')
def management_all(mode = None):
    expr_list = None
    node_list = None
    if mode == 'node':
        node_list = fetch_all_nodes()
    elif mode == 'expr':
        expr_list = fetch_all_expr()
    return render_template('management.html', mode=mode, node_list=node_list, expr_list=expr_list)

def fetch_all_nodes():
    _call_method('refresh')
    stat = _call_method('stat')
    result = stat.get('result', {})
    return result.get('node_id_seen', [])

def fetch_all_expr():
    _call_method('refresh')
    stat = _call_method('stat')
    result = stat.get('result', {})
    return result.get('expr_seen', [])

@app.route('/management/expr/<expr>')
@app.route('/management/node/<node_id>')
def management_single(node_id = None, expr = None):
    expr_list = None
    node_list = None
    if node_id == None:
        node_list = fetch_node_for_expr(expr)
        mode = 'expr'
    elif expr == None:
        expr_list = fetch_expr_for_node_id(node_id)
        mode = 'node'
    return render_template('management.html', mode=mode, node_id = node_id, expr = expr, node_list=node_list, expr_list=expr_list)

def fetch_node_for_expr(expr):
    _call_method('refresh')
    stat = _call_method('stat', expr=expr)
    result = stat.get('result', {})
    return result.get('node_id_seen', [])

def fetch_expr_for_node_id(node_id):
    _call_method('refresh')
    stat = _call_method('stat', node_id=node_id)
    result = stat.get('result', {})
    return result.get('expr_seen', [])

@app.route('/management/action', methods=['GET'])
def management_action():
    if request.args.get('method', 'refresh') == 'stat':
        return render_template('statistics.html', node_id=request.args.get('node', '*'), expr=request.args.get('expr', '*'))
    result = _call_method(request.args.get('method', 'refresh'), request.args.get('node', '*'), request.args.get('expression', '*'))
    success = result.get('result', False)
    return render_template('result.html', mode='hide', success=success, previous=request.args.get('previous', 'management'))


@app.route('/data', methods=['GET'])
def ajax_data():
    _call_method('refresh', request.args.get('node', '*'), request.args.get('expression', '*'))
    stat = _call_method('stat', request.args.get('node', '*'), request.args.get('expression', '*'))
    return json.dumps(stat.get('result', ''))


# @app.route('/statistics/<mode>')
# def statistics_all(mode = None):
#     expr_list = None
#     node_list = None
#     if mode == 'node':
#         node_list = fetch_all_nodes()
#     elif mode == 'expr':
#         expr_list = fetch_all_expr()
#     return render_template('statistics.html', mode=mode, node_list=node_list, expr_list=expr_list)


# @app.route('/statistics')
# @app.route('/statistics/expr/<expr>')
# @app.route('/statistics/node/<node_id>')
# def statistics_single(node_id = None, expr = None):
#     return render_template('statistics.html', node_id=node_id, expr=expr)

def _call_method(method, node_id='*', expr='*'):
    """Make a JSON-RPC call to an OpenCache controller. Print and return the result."""
    call_id = random.randint(1, 999)
    params = {'node' : str(node_id), 'expr' : str(expr)}
    url =  "http://%s:%s" % ('127.0.0.1', '49001')
    try:
        post_data = json.dumps({"id":call_id, "method":method, "params":params, "jsonrpc":"2.0"})
    except Exception as exception:
        print "[ERROR] Could not encode JSON: %s" % exception
    try:
        response_data = urllib.urlopen(url, post_data).read()
        print "[INFO] Sent request: %s" %post_data
        try:
            response_json = json.loads(response_data)
            if response_json['id'] == str(call_id):
                print "[INFO] Received response: %s" %response_json
                return response_json
            else:
                print "[ERROR] Mismatched call ID for response: %s" %response_json
                raise IOError("Mismatched call ID for response: %s" %response_json)
        except Exception as exception:
            print "[ERROR] Could not decode JSON from OpenCache node response: %s" % exception
    except IOError as exception:
        print "[ERROR] Could not connect to OpenCache instance: %s" % exception
        return {}

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')

