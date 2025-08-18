from math import pi, radians
from collections import defaultdict
from yafs.isl_manager import ISLManager

class OnewebISLManager(ISLManager):
    def __init__(self, sim, bw, time_unit, activation_dist):
        super().__init__(sim, bw, time_unit, activation_dist)

    def _link_strategy(self):
        max_links_per_sat = 4
        link_map = {sat_id: [] for sat_id in self.s.static_nodes}

        delta_raan = 360 / 18  # Nº de planos da constelação (ajusta conforme necessário)
        raan_tol = 5  # graus de tolerância para agrupar satélites no mesmo plano

        planos = defaultdict(list)
        coord_to_id = {}

        # 1. Agrupar por plano e ordenar por MO
        for sat_id in self.s.static_nodes:
            node = self.s.topology.G.nodes[sat_id]
            if node["type"] != "SATELLITE":
                continue
            raan = node.get("raan")
            mo = node.get("mo")
            if raan is None or mo is None:
                continue
            plano_id = round(raan / delta_raan)
            planos[plano_id].append((mo, sat_id))

        # 2. Indexar satélites por posição no plano
        for plano_id, sat_list in planos.items():
            sat_list.sort()  # por mean anomaly (mo)
            for pos_id, (mo, sat_id) in enumerate(sat_list):
                coord_to_id[(plano_id, pos_id)] = sat_id

        # 3. Criar ligações determinísticas
        for (plano_id, pos_id), sat_id in coord_to_id.items():
            ligacoes = []
            N_sats = len(planos[plano_id])

            # Intra-plano
            frente = coord_to_id.get((plano_id, (pos_id + 1) % N_sats))
            tras = coord_to_id.get((plano_id, (pos_id - 1) % N_sats))
            if frente: ligacoes.append(frente)
            if tras: ligacoes.append(tras)

            # Inter-plano
            """
            for vizinho_plano in [(plano_id - 1), (plano_id + 1)]:
                viz_id = coord_to_id.get((vizinho_plano % len(planos), pos_id))
                if viz_id: ligacoes.append(viz_id)

            """
            for other_id in ligacoes:
                if len(link_map[sat_id]) < max_links_per_sat and \
                   len(link_map[other_id]) < max_links_per_sat and \
                   other_id not in link_map[sat_id]:
                    link_map[sat_id].append(other_id)
                    link_map[other_id].append(sat_id)

        return link_map
