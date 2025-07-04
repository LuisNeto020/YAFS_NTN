from yafs.isl_manager import ISLManager  # ajuste o caminho se necessário

class EnhancedISLManager(ISLManager):
    def __init__(self, sim, bw, time_unit, activation_dist):
        super().__init__(sim, bw, time_unit, activation_dist)
        self.valid_neighbors = {}  # {sat: [neighbors]} armazenados após _link_strategy

    def _link_strategy(self):
        """
        Calcula e retorna um dicionário com todos os pares de SATÉLITES que
        poderiam se conectar (distância < LoS), mas ainda não conecta.
        """
        satellites = [n for n in self.s.topology.G.nodes if self.s.topology.G.nodes[n]["type"] == "SATELLITE"]
        link_map = {}

        for i, sat in enumerate(satellites):
            link_map[sat] = []

            for other in satellites[i+1:]:
                dist = self._isl_distance(sat, other)
                alt1 = self.s.topology.G.nodes[sat]["altitude"]
                alt2 = self.s.topology.G.nodes[other]["altitude"]
                los = self._los_limit(alt1, alt2)

                if dist <= los:
                    link_map[sat].append(other)
                    link_map.setdefault(other, []).append(sat)

        self.valid_neighbors = link_map
        return link_map

    def get_connected_nodes(self, node_id):
        """
        Retorna nós com quem o node_id pode se conectar (LoS válido).
        """
        return self.valid_neighbors.get(node_id, [])

    def connect_nodes(self, u, v):
        """
        Estabelece conexão entre u e v, se viável e ainda não existente.
        """
        if self.s.topology.G.has_edge(u, v):
            return False  # Já está conectado

        dist = self._isl_distance(u, v)
        alt1 = self.s.topology.G.nodes[u]["altitude"]
        alt2 = self.s.topology.G.nodes[v]["altitude"]
        los = self._los_limit(alt1, alt2)

        if dist > los:
            return False

        pr_in_sec = dist / 299792.458  # km/s
        pr = pr_in_sec * {'s': 1, 'ms': 1000, 'm': 1/60, 'h': 1/3600}.get(self.time_unit, 1)

        self.s.topology.G.add_edge(u, v, BW=self.link_bw, PR=pr)
        print(f"[EnhancedISLManager] Ligados: {u} <-> {v}, dist={dist:.2f} km")
        return True

    def run(self):
        self._link_strategy()