from math import radians, pi, cos, sin, sqrt

class ISLManager(object):
    
    def __init__(self, sim, bw, time_unit, activation_dist):
        self.s = sim
        self.link_bw = bw
        self.time_unit = time_unit
        self.activation_dist = activation_dist
        
    def get_next_activation(self):
        """
        Returns:
            the next time to be activated
        """
        return self.activation_dist.next() 
        
    def update_links(self):
        for sat in self.s.static_nodes:
            if self.s.topology.G.nodes[sat]["type"] == "SATELLITE":
                connections = self._link_strategy(sat)
                for connection in connections:
                    distance = self._isl_distance(sat, connection)
                    # Cálculo do PR: distância (km) / velocidade da luz (km/s)
                    speed_of_light_kms = 299792.458
                    pr_in_seconds = distance / speed_of_light_kms
                    
                    unit_factors = {
                        's': 1,
                        'ms': 1000,
                        'm': 1/60,
                        'h': 1/3600
                    }
                    pr = pr_in_seconds * unit_factors.get(self.time_unit, 1)
                    self.s.topology.G.add_edge(sat, connection, BW=self.link_bw, PR=pr)
                    
    
    def _isl_distance(self, sat_u, sat_v):
        """
        Computes the Euclidean distance between two satellites in spherical coordinates.
        Equation based on provided LoS-aware model.
        """
        
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

        
    def _link_strategy(self, node):
        return []
    
    def run(self):
        self.update_links()