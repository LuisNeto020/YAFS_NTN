from math import radians, pi, cos, sin, sqrt
import matplotlib.pyplot as plt
import os
import networkx as nx
import cartopy.crs as ccrs
import cartopy.feature as cfeature

class ISLManager(object):
    
    def __init__(self, sim, bw, time_unit, activation_dist):
        self.s = sim
        self.link_bw = bw
        self.time_unit = time_unit
        self.activation_dist = activation_dist
        self.EARTH_RADIUS = 6371.0
        
    def get_next_activation(self):
        """
        Returns:
            the next time to be activated
        """
        return self.activation_dist.next() 
        
    def update_links(self):
        link_map = self._link_strategy()

        for sat in link_map.keys():
            edges_to_remove = [
                (u, v) for u, v in self.s.topology.G.edges(sat)
                if self.s.topology.G.nodes[v if u == sat else u]["type"] == "SATELLITE"
            ]
            self.s.topology.G.remove_edges_from(edges_to_remove)
        
        processed_pairs = set()

        for sat, neighbors in link_map.items():
            for neighbor in neighbors:
                pair = tuple(sorted((sat, neighbor)))  # garante ordem única ex: ("SAT-1", "SAT-2")
                if pair in processed_pairs:
                    continue
                processed_pairs.add(pair)

                if not self.s.topology.G.has_edge(sat, neighbor):
                    distance = self._isl_distance(sat, neighbor)
                    alt1 = self.s.topology.G.nodes[sat]["altitude"]
                    alt2 = self.s.topology.G.nodes[neighbor]["altitude"]
                    los_limit = self._los_limit(alt1, alt2)

                    if distance > los_limit:
                        continue  # não conecta se distância > limite LoS

                    speed_of_light_kms = 299792.458
                    pr_in_seconds = distance / speed_of_light_kms

                    unit_factors = {'s': 1, 'ms': 1000, 'm': 1/60, 'h': 1/3600}
                    pr = pr_in_seconds * unit_factors.get(self.time_unit, 1)

                    self.s.topology.G.add_edge(sat, neighbor, BW=self.link_bw, PR=pr)
                    #print(f"Adicionando ISL: {sat} <--> {neighbor}, dist={distance:.2f} km")

                    
    
    def _isl_distance(self, sat_u, sat_v):
        """
        Computes the Euclidean distance between two satellites in spherical coordinates.
        Equation based on provided LoS-aware model.
        """
        try:
            lat_u, lon_u = self.s.topology.G.nodes[sat_u]['sub_pos']
            lat_v, lon_v = self.s.topology.G.nodes[sat_v]['sub_pos']
            
            r1 = self.EARTH_RADIUS + self.s.topology.G.nodes[sat_u]['altitude']
            r2 = self.EARTH_RADIUS + self.s.topology.G.nodes[sat_v]['altitude']

            theta_u = pi / 2 - radians(lat_u) 
            theta_v = pi / 2 - radians(lat_v) 
            epsilon_p = radians(lon_u)
            epsilon_q = radians(lon_v)

            cos_term = (
                cos(theta_u) * cos(theta_v) +
                cos(epsilon_p - epsilon_q) * sin(theta_u) * sin(theta_v)
            )

            distance = sqrt(r1**2 + r2**2 - 2 * r1 * r2 * cos_term)
            return distance
        except KeyError:
            return float('inf')
    
    def _los_limit(self, h1, h2):
        R = self.EARTH_RADIUS
        return sqrt(h1 * (h1 + 2 * R)) + sqrt(h2 * (h2 + 2 * R))

    
    def _save_isl_snapshot(self):
        timestep = self.s.env.now
        folder = "isl_snapshots"
        os.makedirs(folder, exist_ok=True)

        G = self.s.topology.G

        # Extrair posição dos satélites (lat/lon)
        sat_nodes = [n for n in G.nodes if G.nodes[n]["type"] == "SATELLITE"]
        pos = {n: G.nodes[n]["pos"] for n in sat_nodes if "pos" in G.nodes[n]}  # (lat, lon)

        # Setup do mapa com projeção
        fig = plt.figure(figsize=(12, 6))
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_title(f"ISLs at simulation time {timestep}")
        ax.coastlines()
        ax.add_feature(cfeature.BORDERS, linestyle=':')
        ax.gridlines(draw_labels=False)

        # Desenhar satélites
        for node, (lat, lon) in pos.items():
            if G.nodes[node]["constellation_name"] == "cloud_synthetic":
                ax.plot(lon, lat, marker='o', color='red', markersize=3, transform=ccrs.PlateCarree())
            elif G.nodes[node]["constellation_name"] == "edge_synthetic":
                ax.plot(lon, lat, marker='o', color='green', markersize=3, transform=ccrs.PlateCarree())
            else:
                ax.plot(lon, lat, marker='o', color='blue', markersize=3, transform=ccrs.PlateCarree())

        # Desenhar ISLs
        for u, v in G.edges:
            if u in pos and v in pos:
                lat1, lon1 = pos[u]
                lat2, lon2 = pos[v]
                
                if abs(lon1 - lon2) > 180:
                    # Ajustar longitudes para não cruzar o mapa inteiro
                    if lon1 > lon2:
                        lon2 += 360
                    else:
                        lon1 += 360
                
                ax.plot([lon1, lon2], [lat1, lat2], color='gray', linewidth=0.5, transform=ccrs.PlateCarree())

        # Salvar imagem
        filepath = os.path.join(folder, f"isl_{int(timestep)}.png")
        plt.savefig(filepath, bbox_inches='tight')
        plt.close()

        
    def _link_strategy(self):
        return {}
    
    def run(self):
        print(f"[{self.s.env.now}] Executando ISLManager")
        print("Antes de update_links: Nós =", len(self.s.topology.G.nodes), "Arestas =", len(self.s.topology.G.edges))
        self.update_links()
        print("Depois de update_links: Nós =", len(self.s.topology.G.nodes), "Arestas =", len(self.s.topology.G.edges))
        #self._save_isl_snapshot()



class WalkerLikeISLManager(ISLManager):
    def __init__(self, sim, bw, time_unit, activation_dist):
        super().__init__(sim, bw, time_unit, activation_dist)

    def _link_strategy(self):
        max_links_per_sat = 4
        delta_omega = (2 * pi) / 72 
        print(f"Número de static_nodes: {len(self.s.static_nodes)}") 
        link_map = {sat_id: [] for sat_id in self.s.static_nodes}

        def angular_distance(a, b):
            diff = abs(a - b) % (2 * pi)
            return min(diff, 2 * pi - diff)
        
        for sat_id in self.s.static_nodes:
            if sat_id not in self.s.topology.G.nodes:
                continue
            node = self.s.topology.G.nodes[sat_id]
            if node["type"] != "SATELLITE":
                continue
            raan_u = node.get("raan")
            mo_u = node.get("mo")
            if raan_u is None or mo_u is None:
                continue

            intra_plane = []
            inter_plane = []

            for other_id in self.s.static_nodes:
                if other_id == sat_id or other_id not in self.s.topology.G.nodes:
                    continue
                other = self.s.topology.G.nodes[other_id]
                if other["type"] != "SATELLITE":
                    continue

                raan_v = other.get("raan")
                mo_v = other.get("mo")
                if raan_v is None or mo_v is None:
                    continue

                delta_raan = angular_distance(raan_u, raan_v)

                if delta_raan < radians(0.8) and other.get("altitude")== node.get("altitude"):
                    intra_plane.append(other_id)
                else:
                    inter_plane.append(other_id)

            # Ordenar candidatos por distância real
            intra_plane.sort(key=lambda x, sid=sat_id: self._isl_distance(sid, x))
            inter_plane.sort(key=lambda x, sid=sat_id: self._isl_distance(sid, x))

            # Selecionar até 2 de cada tipo
            for group in [intra_plane, inter_plane]:
                count = 0
                for other_id in group:
                    if len(link_map[sat_id]) >= max_links_per_sat:
                        break
                    if len(link_map[other_id]) >= max_links_per_sat:
                        continue
                    if other_id not in link_map[sat_id] and sat_id not in link_map[other_id]:
                        link_map[sat_id].append(other_id)
                        link_map[other_id].append(sat_id)
                        count += 1
                    if count >= 2:
                        break


        return link_map
        

