from yafs.selection import Selection
import numpy as np
import networkx as nx
from collections import defaultdict
from collections import Counter

class WeightGreedySelection(Selection):
    def __init__(self, isl_manager, weights=(0.3, 0.15, 0.25, 0.3)):
        super(WeightGreedySelection, self).__init__()
        self.cache_neighbors = {}
        self.invalid_cache_value = True
        self.isl_manager = isl_manager
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

    def get_path(self, sim, app_name, message, topology_src, alloc_DES, alloc_module, traffic, from_des):
        msg_type = message.name
        src = topology_src
        dst_service = message.dst
        
        if not self.des_cache_built:
            self.des_by_node = defaultdict(list)
            for des_id, node_id in alloc_DES.items():
                self.des_by_node[node_id].append(des_id)
            self.des_cache_built = True

        if self.invalid_cache_value or not self.cache_neighbors:
            self.update_neighbors_cache()
        # ⏹ Caso 1: user_request → deve ser processado localmente
        if msg_type == "user_request":
            self.task_origin_map[message.id] = src  # Rastrear origem
            src_des = self.get_des_for_module_on_node(src, dst_service, app_name, alloc_module, alloc_DES)
            print(f"Processing user_request on {src} with DES {src_des}")
            return [[src]], [src_des]

        # ⏹ Caso 2: task_result → deve retornar ao nó que originou o request
        if msg_type == "task_result":
            original_node = self.task_origin_map.get(message.id, None)
            if original_node is None:
                return [], None
            try:
                path = nx.shortest_path(sim.topology.G, source=src, target=original_node)
                on_des = self.get_des_for_module_on_node(original_node, message.dst, app_name, alloc_module, alloc_DES)
                print(f"Path for task_result from {src} to {original_node}: {on_des}")
                return [path], [on_des]
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return [], None

        # ⏹ Caso 3: task_data → processar com balanceamento + round robin

        # Verificar candidatos
        #DES_dst = alloc_module[app_name][dst_service]
        candidate_nodes = self.cache_neighbors.get(src, [])
        #possible_nodes = [n for n in candidate_nodes if n in DES_dst]

        stats = []  # cada linha é [dist, energy, load, 1/ipt]
        valid_candidates = []
        G = sim.topology.G

        for node in candidate_nodes:
            try:
                distance = self.isl_manager._isl_distance(src, node)
                distance_delay = distance / 300000000
                energy =10 * np.log10(G.nodes[node].get("ENERGY", 0.001))
                #energy = np.log1p(energy)
                #energy = G.nodes[node].get("ENERGY", 0.001)
                
                ipt = G.nodes[node].get("IPT", 100)
                ipt_delay = message.inst / float(ipt)
                load = self.counter[node]
                """
                des_ids_in_node = self.des_by_node.get(node, [])
                for des_id in des_ids_in_node:
                    pipe_id = f"{app_name}{dst_service}{des_id}"
                    queue = sim.consumer_pipes.get(pipe_id)
                    if queue:
                        try:
                            load += len(queue.items)
                        except:
                            pass
                """
                row = [distance_delay, energy, load, ipt_delay]
                stats.append(row)
                valid_candidates.append(node)

            except:
                continue
            
        if not stats:
            return [], None

        # Normalização (0-1)
        stats = np.array(stats)
        mins = stats.min(axis=0)
        maxs = stats.max(axis=0)
        ranges = maxs - mins
        ranges[ranges == 0] = 1
        norm = (stats - mins) / ranges

        # Cálculo ponderado
        weights = np.array(self.weights)
        scores = norm @ weights

        best_idx = np.argmin(scores)
        chosen = valid_candidates[best_idx]
        
        node_type = sim.topology.G.nodes[chosen].get("constellation_name", "").lower()  

        # Define a taxa de contagem por tipo
        if node_type == "cloud_synthetic":
            factor = 16
        elif node_type == "edge_synthetic":
            factor = 4
        else:  # mist ou outro
            factor = 1

        # Incrementa o contador visível apenas quando atinge o fator
        if self.raw_counter[chosen] % factor == 0:
            self.counter[chosen] += 1

        try:
            path = nx.shortest_path(sim.topology.G, source=src, target=chosen)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            print(f"No path found from {src} to {chosen}")
            return [], None
        chosen_des = self.get_des_for_module_on_node(chosen, dst_service, app_name, alloc_module, alloc_DES)
        print(f"Path for task_data from {src} to {chosen}: {chosen_des}")
        return [path], [chosen_des]

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
    
    

