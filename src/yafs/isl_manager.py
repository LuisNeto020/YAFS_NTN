from math import radians, pi, cos, sin, sqrt
import matplotlib.pyplot as plt
import os
import networkx as nx
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import logging

class ISLManager(object):
    
    """
    Manages Inter-Satellite Links (ISLs) in a satellite network simulation.

    This class is responsible for updating, creating, and removing ISLs 
    between satellites according to geometric constraints, bandwidth, 
    and latency considerations.
    """
    
    def __init__(self, sim, bw, time_unit, activation_dist):
        """
        Initialize the ISLManager.

        Args:
            sim: Simulation object that holds the environment and network topology.
            bw (float): Bandwidth assigned to each ISL.
            time_unit (str): Time unit for propagation delay ("s", "ms", "m", "h").
            activation_dist: Distribution object used to determine the next activation time.
        """
        self.s = sim
        self.link_bw = bw
        self.time_unit = time_unit
        self.activation_dist = activation_dist
        self.EARTH_RADIUS = 6371.0
        
    def get_next_activation(self):
        """
        Get the next ISL activation time from the provided distribution.
        
        Returns:
            the next time to be activated
        """
        return self.activation_dist.next() 
    
    def _remove_existing_isl_edges(self, link_map):
        """
        Remove outdated ISLs from the topology.

        Args:
            link_map (dict): Mapping of satellites and their intended neighbors.
        """
        for sat in link_map.keys():
            edges_to_remove = [
                (u, v) for u, v in self.s.topology.G.edges(sat)
                if self.s.topology.G.nodes[v if u == sat else u]["type"] == "SATELLITE"
            ]
            self.s.topology.G.remove_edges_from(edges_to_remove)

        
    def update_links(self):
        """
        Update ISLs based on the link strategy.

        Removes outdated ISLs and creates new ones according to distance 
        and line-of-sight (LoS) constraints. Also calculates propagation 
        delay (PR) based on the distance and speed of light.
        """
        link_map = self._link_strategy()

        self._remove_existing_isl_edges(link_map)
        
        processed_pairs = set()

        for sat, neighbors in link_map.items():
            for neighbor in neighbors:
                pair = tuple(sorted((sat, neighbor)))  # to avoid duplicates 
                if pair in processed_pairs:
                    continue
                processed_pairs.add(pair)

                if not self.s.topology.G.has_edge(sat, neighbor):
                    distance = self._isl_distance(sat, neighbor)
                    alt1 = self.s.topology.G.nodes[sat]["altitude"]
                    alt2 = self.s.topology.G.nodes[neighbor]["altitude"]
                    los_limit = self._los_limit(alt1, alt2)

                    if distance > los_limit:
                        logging.debug(
                            "Skipped ISL %s <-> %s (distance %.2f km > LoS %.2f km)",
                            sat, neighbor, distance, los_limit
                        )
                        continue  # don't create link 

                    speed_of_light_kms = 299792.458
                    pr_in_seconds = distance / speed_of_light_kms

                    unit_factors = {'s': 1, 'ms': 1000, 'm': 1/60, 'h': 1/3600}
                    pr = pr_in_seconds * unit_factors.get(self.time_unit.lower(), 1)

                    self.s.topology.G.add_edge(sat, neighbor, BW=self.link_bw, PR=pr)
                    logging.info(
                        "Added ISL: %s <-> %s (distance=%.2f km, PR=%.4f %s)",
                        sat, neighbor, distance, pr, self.time_unit
                    )

                    
    
    def _isl_distance(self, sat_u, sat_v):
        """
        Compute the Euclidean distance between two satellites in 3D space.

        Args:
            sat_u (str): Identifier of the first satellite node.
            sat_v (str): Identifier of the second satellite node.

        Returns:
            float: Distance in kilometers between the two satellites.
                   Returns infinity if position data is unavailable.
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
        """
        Compute the maximum line-of-sight (LoS) distance between two satellites.

        Args:
            h1 (float): Altitude of the first satellite (km).
            h2 (float): Altitude of the second satellite (km).

        Returns:
            float: Maximum allowed LoS distance (km).
        """
        R = self.EARTH_RADIUS
        return sqrt(h1 * (h1 + 2 * R)) + sqrt(h2 * (h2 + 2 * R))

    
    def _save_isl_snapshot(self):
        """
        Save a visual snapshot of the ISLs at the current simulation time.

        Generates a world map with satellites and their ISLs, 
        storing it as a PNG file inside the `isl_snapshots` folder.
        """
        timestep = self.s.env.now
        folder = "isl_snapshots"
        os.makedirs(folder, exist_ok=True)

        G = self.s.topology.G

        sat_nodes = [n for n in G.nodes if G.nodes[n]["type"] == "SATELLITE"]
        pos = {n: G.nodes[n]["pos"] for n in sat_nodes if "pos" in G.nodes[n]}  # (lat, lon)

        # setup map with projection
        _ = plt.figure(figsize=(12, 6))
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_title(f"ISLs at simulation time {timestep}")
        ax.coastlines()
        ax.add_feature(cfeature.BORDERS, linestyle=':')
        ax.gridlines(draw_labels=False)

        # draw satellites
        for sat_id, (lat, lon) in pos.items():
            ax.plot(lon, lat, marker='o', color='blue', markersize=3, transform=ccrs.PlateCarree())

        # draw edges
        for u, v in G.edges:
            if u in pos and v in pos:
                lat1, lon1 = pos[u]
                lat2, lon2 = pos[v]
                
                if abs(lon1 - lon2) > 180:
                    # ajust longitudes to avoid crossing the entire map
                    if lon1 > lon2:
                        lon2 += 360
                    else:
                        lon1 += 360
                
                ax.plot([lon1, lon2], [lat1, lat2], color='gray', linewidth=0.5, transform=ccrs.PlateCarree())

        # save image
        filepath = os.path.join(folder, f"isl_{int(timestep)}.png")
        plt.savefig(filepath, bbox_inches='tight')
        plt.close()

        
    def _link_strategy(self):
        """
        Define the ISL connection strategy.

        This method should be overridden by subclasses to implement 
        specific ISL connection policies.

        Returns:
            dict: Mapping of satellite IDs to their neighbor satellites.
        """
        return {}
    
    def run(self):
        logging.debug(
            "[%s] Running ISLManager - before update: nodes=%d, edges=%d",
            self.s.env.now,
            len(self.s.topology.G.nodes),
            len(self.s.topology.G.edges),
        )
        self.update_links()
        logging.debug(
            "[%s] After update: nodes=%d, edges=%d",
            self.s.env.now,
            len(self.s.topology.G.nodes),
            len(self.s.topology.G.edges),
        )
        self._save_isl_snapshot()



class WalkerLikeISLManager(ISLManager):
    """
    Implements a Walker-like ISL connection strategy.

    Satellites are connected based on their orbital parameters 
    (RAAN, mean anomaly, altitude), preferring intra-plane and inter-plane 
    connections while limiting the maximum number of links per satellite.
    """
    def __init__(self, sim, bw, time_unit, activation_dist):
        super().__init__(sim, bw, time_unit, activation_dist)
        logging.info("WalkerLikeISLManager initialized with bw=%s, time_unit=%s", bw, time_unit)

    def _link_strategy(self):
        """
        Define a Walker-like ISL strategy.

        Satellites connect to their closest neighbors within the same plane 
        (intra-plane) and across adjacent planes (inter-plane). 
        Each satellite can establish up to 4 links, with a maximum of 
        2 intra-plane and 2 inter-plane connections.

        Returns:
            dict: Mapping of satellite IDs to their selected neighbor satellites.
        """
        max_links_per_sat = 4 
        link_map = {sat_id: [] for sat_id in self.s.static_nodes}
        logging.debug("Starting link strategy for %d nodes", len(self.s.static_nodes))
        
        for sat_id in self.s.static_nodes:
            if sat_id not in self.s.topology.G.nodes:
                logging.warning("Satellite %s not found in topology graph", sat_id) 
                continue 
            node = self.s.topology.G.nodes[sat_id] 
            if node["type"] != "SATELLITE": 
                continue 
            raan_u = node.get("raan") 
            mo_u = node.get("mo") 
            if raan_u is None or mo_u is None: 
                continue
            intra_plane, inter_plane = self._classify_neighbors(sat_id)
            
            logging.debug(
                "Satellite %s classified neighbors: %d intra-plane, %d inter-plane",
                sat_id, len(intra_plane), len(inter_plane)
            )
            
            # ordered by distance
            intra_plane.sort(key=lambda x, sid=sat_id: self._isl_distance(sid, x))
            inter_plane.sort(key=lambda x, sid=sat_id: self._isl_distance(sid, x))

            # select 2 intra-plane and 2 inter-plane links
            for group in [intra_plane, inter_plane]:
                self._assign_links(sat_id, group, link_map, max_links_per_sat)
        logging.info("Finished building link map with %d satellites", len(link_map))
        return link_map
    
    def _classify_neighbors(self, sat_id):
        """
        Classify neighbors of a satellite into intra-plane or inter-plane.

        Args:
            sat_id (str): ID of the satellite.

        Returns:
            tuple[list[str], list[str]]: (intra_plane, inter_plane) neighbors.
        """
        node = self.s.topology.G.nodes[sat_id]
        raan_u = node["raan"]
        altitude_u = node["altitude"]

        intra_plane, inter_plane = [], []

        def angular_distance(a, b):
            diff = abs(a - b) % (2 * pi)
            return min(diff, 2 * pi - diff)

        for other_id in self.s.static_nodes:
            if other_id == sat_id or other_id not in self.s.topology.G.nodes:
                continue
            other = self.s.topology.G.nodes[other_id]
            if other.get("type") != "SATELLITE":
                continue
            if other.get("raan") is None or other.get("mo") is None:
                continue

            delta_raan = angular_distance(raan_u, other["raan"])
            if delta_raan < radians(0.8) and other.get("altitude") == altitude_u:
                intra_plane.append(other_id)
            else:
                inter_plane.append(other_id)

        return intra_plane, inter_plane
    
    def _assign_links(self, sat_id, candidates, link_map, max_links_per_sat):
        """
        Assign ISLs between a satellite and candidates, respecting max limits.

        Args:
            sat_id (str): The satellite ID.
            candidates (list[str]): Candidate neighbor satellites.
            link_map (dict): Current mapping of links.
            max_links_per_sat (int): Maximum links allowed per satellite.
        """
        count = 0
        for other_id in candidates:
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
        

