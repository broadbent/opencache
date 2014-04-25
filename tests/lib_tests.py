#!/usr/bin/env python2.7

import opencache.lib.opencachelib as lib

def test_expr_split():
    root, path = lib.expr_split('127.0.0.1/path/to/object')
    assert root == '127.0.0.1'
    assert path == 'path/to/object'