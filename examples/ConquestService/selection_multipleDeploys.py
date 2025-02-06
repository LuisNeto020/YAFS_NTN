from yafs.selection import Selection
from yafs.topology import *
import networkx as nx

class DeviceSpeedAwareRouting(Selection):

    def __init__(self):
        self.cache = {}
        self.invalid_cache_value = True

        self.controlServices = {}
        # key: a service
        # value : a list of idDevices
        super(DeviceSpeedAwareRouting, self).__init__()

    def compute_BEST_DES(self, node_src, alloc_DES, sim, DES_dst,message):
        """
        Computes the best Destination Entity (DES) based on the network topology.

        Args:
            node_src (int): Source node.
            alloc_DES (dict): Mapping of DES IDs to topology nodes.
            sim (Sim): Simulation instance.
            DES_dst (list): List of available DESs for the service.
            message (Message): Message to be routed.

        Returns:
            minPath: The shortest path from the source to the destination.
            bestDES: The best destination for the message.
        """
        try:

            bestLong = float('inf')
            minPath = []
            bestDES = []
            #print(len(DES_dst))
            for dev in DES_dst:
                #print("DES :",dev)
                node_dst = alloc_DES[dev]
                path = list(nx.shortest_path(sim.topology.G, source=node_src, target=node_dst))
                long = len(path)

                if  long < bestLong:
                    bestLong = long
                    minPath = path
                    bestDES = dev

            #print(bestDES,minPath)
            return minPath, bestDES

        except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
            self.logger.warning("There is no path between two nodes: %s - %s " % (node_src, node_dst))
            # print("Simulation ends?")
            return [], None

    def get_path(self, sim, app_name, message, topology_src, alloc_DES, alloc_module, traffic, from_des):
        """
        Obtains the ideal path for the message.

        Args:
            sim (Sim): Simulation instance.
            app_name (str): Application name.
            message (Message): Message to be routed.
            topology_src (int): Source node.
            alloc_DES (dict): Mapping of DES IDs to topology nodes.
            alloc_module (dict): Mapping of modules to DES IDs.
            traffic (obj): Network traffic.
            from_des (int): Source DES ID.

        Returns:
            path: A list containing the path for the message.
            des: A list containing the destination for the message.
        """
        node_src = topology_src #entity that sends the message

        # Name of the service
        service = message.dst

        DES_dst = alloc_module[app_name][message.dst] #module sw that can serve the message

        #print("Enrouting from SRC: %i  -<->- DES %s"%(node_src,DES_dst))

        #The number of nodes control the updating of the cache. If the number of nodes changes, the cache is totally cleaned.
        if self.invalid_cache_value:
            self.invalid_cache_value = False
            self.cache = {}

        if (node_src,tuple(DES_dst)) not in self.cache.keys():
            self.cache[node_src,tuple(DES_dst)] = self.compute_BEST_DES(node_src, alloc_DES, sim, DES_dst,message)

        path, des = self.cache[node_src,tuple(DES_dst)]
        self.controlServices[(node_src, service)] = (path, des)

        return [path], [des]

    def get_path_from_failure(self, sim, message, link, alloc_DES, alloc_module, traffic, ctime, from_des):
        """
        Obtains the ideal path when a failure occurs.

        Args:
            sim (Sim): Simulation instance.
            message (Message): Message to be routed.
            link (tuple): Failed link.
            alloc_DES (dict): Mapping of DES IDs to topology nodes.
            alloc_module (dict): Mapping of modules to DES IDs.
            traffic (obj): Network traffic.
            ctime (int): Current simulation time.
            from_des (int): Source DES ID.

        Returns:
            concPath: A list containing the new path for the message.
            des: The destination for the message.
        """
        # print("Example of enrouting")
        #print(message.path # [86, 242, 160, 164, 130, 301, 281, 216])
        #print(message.dst_int  # 301)
        #print(link #(130, 301) link is broken! 301 is unreacheble)

        idx = message.path.index(link[0])
        #print("IDX: ",idx)
        if idx == len(message.path):
            # The node who serves ... not possible case
            return [],[]
        else:
            node_src = message.path[idx] #In this point to the other entity the system fail
            # print("SRC: ",node_src # 164)

            node_dst = message.path[len(message.path)-1]
            # print("DST: ",node_dst #261)
            # print("INT: ",message.dst_int #301)

            path, des = self.get_path(sim,message.app_name,message,node_src,alloc_DES,alloc_module,traffic,from_des)
            if len(path[0])>0:
                # print(path # [[164, 130, 380, 110, 216]])
                # print(des # [40])

                concPath = message.path[0:message.path.index(path[0][0])] + path[0]
                # print(concPath # [86, 242, 160, 164, 130, 380, 110, 216])
                newINT = node_src #path[0][2]
                # print(newINT # 380)

                message.dst_int = newINT
                return [concPath], des
            else:
                return [],[]


