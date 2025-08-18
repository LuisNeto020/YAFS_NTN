from yafs.selection import Selection
import networkx as nx

class TradiPollingSelection(Selection):
    def __init__(self, isl_manager):
        super(TradiPollingSelection, self).__init__()
        self.cache_neighbors = {}
        self.invalid_cache_value = True
        self.isl_manager = isl_manager
        self.task_origin_map = {}  # Para rastrear o nó de origem de user_request
        self.tp_index = 0
        


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
        
        candidate_nodes = self.cache_neighbors.get(src, [])
        
        sorted_candidates = sorted(candidate_nodes)  # ordem determinística
        total = len(sorted_candidates)

        for i in range(total):
            idx = (self.tp_index + i) % total
            candidate = sorted_candidates[idx]

            des_id = self.get_des_for_module_on_node(candidate, dst_service, app_name, alloc_module, alloc_DES)
            if des_id is not None:
                try:
                    path = nx.shortest_path(sim.topology.G, source=src, target=candidate)
                    self.tp_index = (idx + 1) % total  # avança o índice global
                    return [path], [des_id]
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue

        return [], None 

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
    
    

