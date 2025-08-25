import math
import logging
from skyfield.api import wgs84

class Coverage(object):
    """
        Base class for managing coverage and connectivity policies in YAFS simulations.
        
        Args:
                activation_dist: Distribution object that determines activation times.
                sim (yafs.core.Sim): Simulation instance.
                bw_ter (float): Bandwidth for terrestrial connections.
                pr_ter (float): Propagation delay for terrestrial connections.
                bw_sat (float): Bandwidth for satellite connections.
                time_unit (str): Time unit used for delays ("s", "ms", "m", "h").
    """
    UNIT_FACTORS = {
        "s": 1,
        "ms": 1000,
        "m": 1 / 60,
        "h": 1 / 3600,
    }
    
    def __init__(self, activation_dist, sim, bw_ter=0, pr_ter=0, bw_sat=0, time_unit="s"):
        self.activation_dist = activation_dist
        self.s = sim
        self.user_connections = {}
        self.bw_ter = bw_ter
        self.pr_ter = pr_ter
        self.bw_sat = bw_sat
        self.time_unit = time_unit
        
    def connectivity_policy(self, possible_conections, mobile_node):
        """
            Defines the policy for selecting which connection to establish between possible candidate network nodes.

            Args:
                possible_conections (list): List of nodes available for connection.
                mobile_node (node id): The mobile node being considered.

            Returns:
                list: Selected connections.
            .. note:: This method should be overridden in subclasses to implement specific connectivity policies.   
        """
        pass
       
    def verify_coverage_static_node(self, static_node, mobile_node):
        """
            Check if a static node (communications tower, router, etc.) provides coverage for the given mobile node.

            Args:
                static_node (): Identifier of the static node.
                mobile_node (): Identifier of the mobile node.

            Returns:
                bool: True if coverage is available, False otherwise.
            .. note:: This method should be overridden in subclasses to implement specific coverage checks.
        """
        pass
     
    def verify_coverage_satellite_node(self, satellite_node, mobile_node):
        """
            Check if a satellite node provides coverage for the given mobile node.

            Args:
                satellite_node (): Identifier of the satellite node.
                mobile_node (): Identifier of the mobile node.

            Returns:
                bool: True if coverage is available, False otherwise.
            .. note:: This method should be overridden in subclasses to implement specific coverage checks.
        """
        pass  
           
    def get_next_activation(self):
        """
            Get the next activation time from the distribution.

            Returns:
                float: Next activation timestamp.
        """
        return self.activation_dist.next() 
    
    def __add_connections(self, user, new_connections, current_connections):
        """
            Add new connections for a user to the simulation topology.

            Args:
                user: The user node.
                new_connections (list): List of candidate nodes to connect.
                current_connections (list): Existing connections of the user.
        """
        for node in new_connections:
            if node not in current_connections:
                # verify if the node and user exist in the topology
                if user in self.s.topology.G.nodes and node in self.s.topology.G.nodes:
                    # if the node is a satellite, calculate the propagation delay
                    if self.s.topology.G.nodes[node]["type"] == "SATELLITE":
                        
                        lat1, lon1 = self.s.topology.G.nodes[user]['pos']
                        lat2, lon2 = self.s.topology.G.nodes[node]['sub_pos']
                        bluffton = wgs84.latlon(lat1, lon1)
                        
                        satellite = wgs84.latlon(
                            lat2, lon2, self.s.topology.G.nodes[node]['altitude']*1000
                        )
                        
                        t = self.s.topology.G.nodes[node]['time']
                        difference = satellite - bluffton
                        topocentric = difference.at(t)
                        _, _, distance =topocentric.altaz()
                        
                        distance_km = distance.km

                        # Calculate propagation delay (PR): distance (km) / speed of light (km/s)
                        speed_of_light_kms = 299792.458
                        pr_in_seconds = distance_km / speed_of_light_kms
                        
                        pr = pr_in_seconds * self.UNIT_FACTORS.get(self.time_unit.lower(), 1)
                        
                        self.s.topology.G.add_edge(user, node, BW=self.bw_sat, PR=pr)
                        logging.info(
                            f"Added SATELLITE connection {user} <-> {node} | PR={pr:.6f} {self.time_unit} at t={self.s.env.now}"
                        )
                    else:
                        self.s.topology.G.add_edge(user, node, BW=self.bw_ter, PR=self.pr_ter)
                        logging.info(
                            f"Added STATIC connection {user} <-> {node} | PR={self.pr_ter} {self.time_unit} at t={self.s.env.now}"
                        )
                
                    self.user_connections.setdefault(user, []).append(node)
    
    def __remove_connections(self, user, new_connections, current_connections ):
        """
        Remove outdated connections that are no longer valid.

        Args:
            user: The user node.
            new_connections (list): Nodes that should remain connected.
            current_connections (list): Active connections in the previous timestep.
        """
        for current_node in current_connections:
            if current_node not in new_connections:
                self.__remove_single_connection(user, current_node)

    def __remove_single_connection(self, user, current_node):
        """
        Remove a specific connection if it exists in the topology.

        Args:
            user: The user node.
            current_node: The node to disconnect.
        """
        if user not in self.s.topology.G.nodes:
            return
        if current_node not in self.s.topology.G.nodes:
            return
        if not self.s.topology.G.has_edge(current_node, user):
            return

        self.s.topology.G.remove_edge(current_node, user)
        self.user_connections[user].remove(current_node)

        if not self.user_connections[user]:
            del self.user_connections[user]

        logging.info(
            f"Removed connection {user} <-> {current_node} at t={self.s.env.now}"
        )
    
    def update_connection(self):
        """
        Update user connections by checking coverage and applying the
        connectivity policy. Adds and removes edges in the topology.
        """
        for user in self.s.mobile_users:
            possible_connections = self.__get_possible_connections(user)
            selected_connections = self.connectivity_policy(possible_connections, user)
            current_connections = set(self.user_connections.get(user, []))

            self.__remove_connections(user, selected_connections, current_connections)
            self.__add_connections(user, selected_connections, current_connections)


    def __get_possible_connections(self, user):
        """
        Get all possible nodes that cover a given user.

        Args:
            user: The user node.

        Returns:
            list: Nodes within coverage.
        """
        possible = []
        if user not in self.s.topology.G.nodes:
            return possible

        for node in self.s.static_nodes:
            if node not in self.s.topology.G.nodes:
                continue

            node_type = self.s.topology.G.nodes[node]["type"]

            coverage_check = False
            if node_type == "STATIC":
                coverage_check = self.verify_coverage_static_node(node, user)
            elif node_type == "SATELLITE":
                coverage_check = self.verify_coverage_satellite_node(node, user)

            if coverage_check:
                possible.append(node)

        return possible

            
            
    def run(self):
        """
        This method will be invoked during the simulation to update the connections based on the coverage and connectivity policies.    
        """
        
        self.update_connection()
        
    
class CircleCoverage(Coverage):
    """
    Concrete implementation of Coverage that uses circular areas of coverage.
    """
    def __init__(self, activation_dist, sim, radius,bw_ter=0, pr_ter=0, bw_sat=0, time_unit="s"):
        """
            Initialize CircleCoverage with a fixed radius.

            Args:
                activation_dist: Distribution object that determines activation times.
                sim (yafs.core.Sim): Simulation instance.
                radius (float): Coverage radius in kilometers.
                bw_ter (float): Bandwidth for terrestrial connections.
                pr_ter (float): Propagation delay for terrestrial connections.
                bw_sat (float): Bandwidth for satellite connections.
                time_unit (str): Time unit used for delays ("s", "ms", "m", "h").
        """
        super().__init__(
            activation_dist=activation_dist,
            sim=sim,
            bw_ter=bw_ter,
            pr_ter=pr_ter,
            bw_sat=bw_sat,
            time_unit=time_unit
        )

        self.radius = radius  # coverage radius in kilometers
    
    def calculate_distance(self, node1, node2):
        """
        Calculate the geodesic distance between two nodes using Haversine formula.

        Args:
            node1: First node identifier.
            node2: Second node identifier.

        Returns:
            float: Distance in kilometers.
        """
        # Radius of the Earth in kilometers
        R = 6371.0
        
        # obtaining latitude and longitude of the nodes
        lat1, lon1 = self.s.topology.G.nodes[node1]['pos']
        lat2, lon2 = self.s.topology.G.nodes[node2]['pos']
        
        # Converting from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Differences between latitudes and longitudes
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Haversine formula
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        # Distance in kilometres
        distance = R * c
        return distance
    
    def verify_coverage_static_node(self, static_node, mobile_node):
        # Check if a static node provides coverage for the given mobile node.
        distance = self.calculate_distance(static_node, mobile_node)
        return distance <= self.radius
    
    def verify_coverage_satellite_node(self, satellite_node, mobile_node):
        # Check if a satellite node provides coverage for the given mobile node.
        radius = self.s.topology.G.nodes[satellite_node].get("coverage_radius_km", 0)
        distance = self.calculate_distance(satellite_node, mobile_node)
        return distance <= radius
    
    def connectivity_policy(self, possible_connections, mobile_node):
        """
        Connectivity policy: choose the closest available node.

        Args:
            possible_connections (list): Candidate nodes with coverage.
            mobile_node: The mobile node.

        Returns:
            list: Nodes to connect (at most one, the closest).
        """
        
        if self.s.topology.G.nodes[mobile_node]["type"] in ("CLOUD", "EMERGENCY_TIME"):
            possible_connections = [
                node for node in possible_connections if self.s.topology.G.nodes[node]["type"] == "SATELLITE"
            ]
        
        if not possible_connections:
            return []
        
        # Find the nearest node
        closest_node = min(
            possible_connections,
            key=lambda node: self.calculate_distance(node, mobile_node),
        )
        
        return [closest_node] 
