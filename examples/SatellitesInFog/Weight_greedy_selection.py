from yafs.selection import Selection
import numpy as np
import networkx as nx
from collections import defaultdict
from collections import Counter

class WeightGreedySelection(Selection):
    def __init__(self, weights=(0.5, 0.3, 0.2)):
        super(WeightGreedySelection, self).__init__()
        self.cache_neighbors = {}
        self.invalid_cache_value = True
        self.isl_manager = None
        self.task_origin_map = {}  # Para rastrear o nó de origem de user_request
        self.weights = weights
        self.des_by_node = None  # Ou {}
        self.des_cache_built = False
        self.counter = Counter()
        self.raw_counter = Counter()



    def update_neighbors_cache(self):
        G = self.isl_manager.s.topology.G
        self.cache_neighbors = {}

        for node in G.nodes:
            if G.nodes[node]["type"] != "SATELLITE":
                continue

            neighbors = []
            for candidate in G.nodes:
                if node == candidate:
                    continue
                if G.nodes[candidate]["type"] != "SATELLITE":
                    continue

                distance = self.isl_manager._isl_distance(node, candidate)
                alt1 = G.nodes[node]["altitude"]
                alt2 = G.nodes[candidate]["altitude"]
                los_limit = self.isl_manager._los_limit(alt1, alt2)

                if distance <= los_limit:
                    neighbors.append(candidate)

            self.cache_neighbors[node] = neighbors

        self.invalid_cache_value = False
        
    def compute_BEST_DES(self, node_src, alloc_DES, sim, DES_dst,message):
        """
                Computes the best destination based on device speed awareness.

                Args:
                    node_src: Source node.
                    alloc_DES: Allocation of DES.
                    sim: Simulation object.
                    DES_dst: Destination DES.
                    message: Message object.

                Returns:
                    minPath: The shortest path from the source to the destination.
                    bestDES: The best destination for the message.
        """
        try:
            bestLong = float('inf')
            minPath = []
            bestDES = []
            moreDES = []
            #print len(DES_dst)
            for dev in DES_dst:
                node_dst = alloc_DES[dev]
                path = list(nx.shortest_path(sim.topology.G, source=node_src, target=node_dst))
                long = len(path)

                if long < bestLong:
                    bestLong = long
                    minPath = path
                    bestDES = dev
                    moreDES = []
                elif long == bestLong:
                    # Another instance service is deployed in the same node
                    if len(moreDES)==0:
                        moreDES.append(bestDES)
                    moreDES.append(dev)


            # There are two or more options in a node: #ROUND ROBIN Schedule
            if len(moreDES)>0:
                ### RETURN
                bestValue = 0
                minCounter =  float('inf')
                for idx,service in enumerate(moreDES):
                    if not service in self.counter:
                        return minPath, service
                    else:
                        if minCounter < self.counter[service]:
                            minCounter = self.counter
                            bestValue = idx
                return minPath, moreDES[bestValue]
            else:
                return minPath, bestDES

        except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
            self.logger.warning("There is no path between two nodes: %s - %s " % (node_src, node_dst))
            # print("Simulation must ends?)"
            return [], None


    def get_path(self, sim, app_name, message, topology_src, alloc_DES, alloc_module, traffic, from_des):
        msg_type = message.name
        src = topology_src
        dst_service = message.dst
        
        if not self.des_cache_built:
            self.des_by_node = defaultdict(list)
            for des_id, node_id in alloc_DES.items():
                self.des_by_node[node_id].append(des_id)
            self.des_cache_built = True

        #if self.invalid_cache_value or not self.cache_neighbors:
        #    self.update_neighbors_cache()
            
        G = sim.topology.G
        src_type = G.nodes[src].get("type", None)
        
        # Caso para user_request ou similares, processar localmente no fog
        if msg_type == "sensor_data":
            #self.task_origin_map[message.id] = src  # Rastrear origem
            src_des = self.get_des_for_module_on_node(src, dst_service, app_name, alloc_module, alloc_DES)
            return [[src]], [src_des]
        
        # Se nó for FOG ou outro tipo estático, processa localmente ou faz seleção entre fog nodes
        if msg_type == "raw_data_to_cloud" and src_type == "MOBILE":
            neighbors = list(G.neighbors(src))
            if G.nodes[neighbors[0]]["type"] == "STATIC":
                # Pode usar lógica parecida com seu weight greedy para escolher o fog node que fará o processamento
                candidate_fog_nodes = [n for n in G.nodes if G.nodes[n].get("type") == "STATIC" or G.nodes[n].get("type") == "CLOUD"]
                stats = []
                valid_candidates = []
                if not candidate_fog_nodes:
                    return [], None
                
                for node in candidate_fog_nodes:
                    try:
                        # Número de hops entre src e node
                        path = nx.shortest_path(G, source=src, target=node)
                        hops = len(path) - 1  # número de saltos

                        ipt = G.nodes[node].get("IPT", 100)
                        ipt_delay = message.inst / float(ipt)

                        load = self.counter[node]

                        # Salva: [hops, load, ipt_delay]
                        row = [hops, load, ipt_delay]
                        stats.append(row)
                        valid_candidates.append(node)

                    except Exception:
                        continue

                if not stats:
                    return [], None

                # Normalização
                stats = np.array(stats, dtype=float)
                mins = stats.min(axis=0)
                ranges = stats.max(axis=0) - mins
                ranges[ranges == 0] = 1  # evitar divisão por zero
                norm = (stats - mins) / ranges

                # Aplicar pesos apenas a [hops, load, ipt_delay]
                # Por exemplo: (0.4, 0.3, 0.3)
                weights = np.array(self.weights)[:3]
                scores = norm @ weights

                best_idx = np.argmin(scores)
                fog_node = valid_candidates[best_idx]
                
                try:
                    path = nx.shortest_path(G, source=src, target=fog_node)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    return [], None
                
                chosen_des = self.get_des_for_module_on_node(fog_node, dst_service, app_name, alloc_module, alloc_DES)
                
                self.counter[fog_node] += 1
                
                return [path], [chosen_des]
            else:
                # Encontrar nós cloud disponíveis
                cloud_nodes = [n for n in G.nodes if G.nodes[n].get("type", "") == "CLOUD"]
                
                if not cloud_nodes:
                    print("No cloud nodes found")
                    return [], None
                
                # Escolher o cloud node "melhor" — aqui pode ser o que estiver com menor carga ou outro critério
                # Para simplicidade, escolher o cloud node com menor load (contador)
                cloud_node = min(cloud_nodes, key=lambda n: self.counter[n])
                
                try:
                    path = nx.shortest_path(G, source=src, target=cloud_node)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    return [], None
                
                chosen_des = self.get_des_for_module_on_node(cloud_node, dst_service, app_name, alloc_module, alloc_DES)
                
                # Atualiza contadores
                self.counter[cloud_node] += 1
                
                return [path], [chosen_des]

        node_src = topology_src #entity that sends the message
        service = message.dst         # Name of the service
        DES_dst = alloc_module[app_name][message.dst] #module sw that can serve the message

        #The number of nodes control the updating of the cache. If the number of nodes changes, the cache is totally cleaned.
        path, des = self.compute_BEST_DES(node_src, alloc_DES, sim, DES_dst,message)

        try:
            dc = int(des)
            #self.counter[dc] += 1
            #self.controlServices[(node_src, service)] = (path, des)
        except TypeError: # The node is not linked with other nodes
            return [], None

        return [path], [des]

    def clear_routing_cache(self):
        self.invalid_cache_value = True
        self.cache_neighbors = {}
        
    def get_des_for_module_on_node(self, node_id, module_name, app_name, alloc_module, alloc_DES):
        # 1. Obtemos todos os DES que estão no node_id
        des_ids_in_node = [des_id for des_id, n in alloc_DES.items() if n == node_id]

        # 2. Obtemos os DES que implementam o módulo (dentro dessa app)
        if app_name not in alloc_module:
            return None
        if module_name not in alloc_module[app_name]:
            return None
        des_ids_with_module = alloc_module[app_name][module_name]

        # 3. Procuramos o DES que está nos dois conjuntos
        for des_id in des_ids_in_node:
            if des_id in des_ids_with_module:
                return des_id

        return None  # Nenhum encontrado
    
    def get_path_from_failure(self, sim, message, link, alloc_DES, alloc_module, traffic, ctime, from_des):
        """
            Gets a new path for a message in case of failure.

            Args:
                sim: Simulation object.
                message: Message object.
                link: Link object.
                alloc_DES: Allocation of Destination End System.
                alloc_module: Allocation of modules.
                traffic: Traffic object.
                ctime: Current time.
                from_des: Source of the message.

            Returns:
                concPath: A list containing the new path for the message.
                des: The destination for the message.
        """
        idx = message.path.index(link[0])
        #print "IDX: ",idx
        if idx == len(message.path):
            # The node who serves ... not possible case
            return [],[]
        else:
            node_src = message.path[idx] #In this point to the other entity the system fail
            # print "SRC: ",node_src # 164

            node_dst = message.path[len(message.path)-1]
            # print "DST: ",node_dst #261
            # print "INT: ",message.dst_int #301

            path, des = self.get_path(sim,message.app_name,message,node_src,alloc_DES,alloc_module,traffic,from_des)
            if len(path) > 0 and len(path[0])>0:
                # print path # [[164, 130, 380, 110, 216]]
                # print des # [40]

                concPath = message.path[0:message.path.index(path[0][0])] + path[0]
                # print concPath # [86, 242, 160, 164, 130, 380, 110, 216]
                newINT = node_src #path[0][2]
                # print newINT # 380

                message.dst_int = newINT
                return [concPath], des
            else:
                return [],[]

    
    

