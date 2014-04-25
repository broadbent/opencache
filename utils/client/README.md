# OpenCache Client #

A simple JSON-RPC Client for OpenCache. Run with:

```bash
$ python jsonrpc-client.py
```

For more details on usage, use the `-h` flag.

Also includes a _very_ simple HTTP server and client in `/http`. To run the server, use:

```bash
$ python http-server.py
```

This will serve the files found in the same directory: `one.txt`,`two.txt`,`three.txt`.

To run the client, use: 

```bash
$ python http-client.py
```

This will continously request the same three files.