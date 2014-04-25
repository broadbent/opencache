from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.topolib import TreeTopo

tree4 = TreeTopo(depth=2,fanout=2)
net = Mininet(topo=tree4, build=False )
c = RemoteController( 'c0', ip='127.0.0.1' )
net.addController(c)
net.build()
net.start()
h1, h2, h3, h4 = net.getNodeByName('h1', 'h2', 'h3', 'h4')
print h1.cmd('opencache --controller --config /home/mininet/opencache/examples/config/controller.conf &')
print h2.cmd('python /home/mininet/opencache/utils/client/http/http-server.py &')
print h3.cmd('opencache --node --config /home/mininet/opencache/examples/config/node.conf &s')
#modify example scripts to include command line options - client
print h4.cmd('python /home/mininet/opencache/utils/client/http/http-client.py %s' % h2.IP())
net.stop()