import math
from skyfield.api import wgs84

class Coverage(object):
    def __init__(self, activation_dist, sim, bw_ter=0, pr_ter=0, bw_sat=0, time_unit="s"):
        self.activation_dist = activation_dist
        self.s = sim
        self.user_connections = {}
        self.bw_ter = bw_ter
        self.pr_ter = pr_ter
        self.bw_sat = bw_sat
        self.time_unit = time_unit
        
    def connectivity_policy(self, possible_conections, mobile_node):
        None
       
    def verify_coverage_static_node(self, static_node, mobile_node):
        None
     
    def verify_coverage_satellite_node(self, satellite_node, mobile_node):
        None  
           
    def get_next_activation(self):
        """
        Returns:
            the next time to be activated
        """
        return self.activation_dist.next() 
    
    def __add_connections(self, user, new_connections, current_connections):
        for node in new_connections:
            if node not in current_connections:
                # Verificar se o nó e o usuário existem na topologia
                if user in self.s.topology.G.nodes and node in self.s.topology.G.nodes:
                    # Se a conexão ainda não existe, adicione a aresta na topologia
                    if self.s.topology.G.nodes[node]["type"] == "SATELLITE":
                        lat1, lon1 = self.s.topology.G.nodes[user]['pos']
                        lat2, lon2 = self.s.topology.G.nodes[node]['sub_pos']
                        bluffton = wgs84.latlon(lat1, lon1)
                        
                        satellite = wgs84.latlon(lat2, lon2, self.s.topology.G.nodes[node]['altitude']*1000)
                        t = self.s.topology.G.nodes[node]['time']
                        difference = satellite - bluffton
                        
                        topocentric = difference.at(t)
                        
                        _, _, distance =topocentric.altaz()
                        
                        distance_km = distance.km

                        # Cálculo do PR: distância (km) / velocidade da luz (km/s)
                        speed_of_light_kms = 299792.458
                        pr_in_seconds = distance_km / speed_of_light_kms
                        
                        unit_factors = {
                            's': 1,
                            'ms': 1000,
                            'm': 1/60,
                            'h': 1/3600
                        }
                        pr = pr_in_seconds * unit_factors.get(self.time_unit, 1)
                        
                        self.s.topology.G.add_edge(user, node, BW=self.bw_sat, PR=pr)
                        print("ligação entre %s e %s com pr %s", node, user, pr, self.s.env.now)
                    else:
                        self.s.topology.G.add_edge(user, node, BW=self.bw_ter, PR=self.pr_ter)
                        print("ligação entre %s e %s", node, user, self.s.env.now)
                
                    self.user_connections.setdefault(user, []).append(node)
    
    def __remove_connections(self, user, new_connections, current_connections ):
        for current_node in current_connections:
            if current_node not in new_connections:
                # Verificar se o nó e o usuário existem na topologia antes de remover a aresta
                if user in self.s.topology.G.nodes and current_node in self.s.topology.G.nodes:
                    if self.s.topology.G.has_edge(current_node, user):
                        self.s.topology.G.remove_edge(current_node, user)
                        self.user_connections[user].remove(current_node)
                        if not self.user_connections[user]:
                            del self.user_connections[user]
                        print("removida ligação entre %s e %s", current_node, user, self.s.env.now)

    
    def update_connection(self):
        for user in self.s.mobile_users:
            possible_conection = list()
            for static in self.s.static_nodes:
                if user in self.s.topology.G.nodes and static in self.s.topology.G.nodes:
                    if self.s.topology.G.nodes[static]["type"] == "STATIC":
                        if self.verify_coverage_static_node(static, user):
                            possible_conection.append(static)
                    elif self.s.topology.G.nodes[static]["type"] == "SATELLITE":
                        if self.verify_coverage_satellite_node(static, user):
                            possible_conection.append(static)
            connections = self.connectivity_policy(possible_conection, user)
                
            # Obter as conexões atuais do usuário
            current_connections = set(self.user_connections.get(user, []))
            # Remover conexões obsoletas
            self.__remove_connections(user, connections, current_connections)
            # Adicionar novas conexões
            self.__add_connections(user, connections, current_connections)
            
            
    def run(self):
        """
        
        This method will be invoked during the simulation to change the assignment of the modules to the topology
        Args:
            sim (:mod: yafs.core.Sim)
        """
        
        self.update_connection()
        
    
class CircleCoverage(Coverage):
    def __init__(self, activation_dist, sim, radius,bw_ter=0, pr_ter=0, bw_sat=0, time_unit="s"):
        super().__init__(
            activation_dist=activation_dist,
            sim=sim,
            bw_ter=bw_ter,
            pr_ter=pr_ter,
            bw_sat=bw_sat,
            time_unit=time_unit
        )

        self.radius = radius  # Raio de cobertura em km
    
    def calculate_distance(self, node1, node2):
        """
        Calcula a distância geodésica entre dois nós usando a fórmula Haversine.
        """
        # Raio da Terra em km
        R = 6371.0
        
        # Obtendo as coordenadas (latitude, longitude) dos nós
        lat1, lon1 = self.s.topology.G.nodes[node1]['pos']
        lat2, lon2 = self.s.topology.G.nodes[node2]['pos']
        
        # Convertendo de graus para radianos
        lat1 = math.radians(lat1)
        lon1 = math.radians(lon1)
        lat2 = math.radians(lat2)
        lon2 = math.radians(lon2)
        
        # Diferenças entre latitudes e longitudes
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Fórmula Haversine
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        # Distância em km
        distance = R * c
        return distance
    
    def verify_coverage_static_node(self, static_node, mobile_node):
        """
        Verifica se a distância entre static_node e mobile_node é menor que o raio
        """
        distance = self.calculate_distance(static_node, mobile_node)
        #print("distancias", distance)
        return distance <= self.radius
    
    def verify_coverage_satellite_node(self, satellite_node, mobile_node):
        """
        Mesmo que para static_node
        """
        radius = self.s.topology.G.nodes[satellite_node].get("coverage_radius_km", 0)
        distance = self.calculate_distance(satellite_node, mobile_node)
        return distance <= radius
    
    def connectivity_policy(self, possible_connections, mobile_node):
        """
        Retorna o nó mais próximo entre os possíveis nós com cobertura
        """
        
        if self.s.topology.G.nodes[mobile_node]["type"] in ("CLOUD", "EMERGENCY_TIME"):
            possible_connections = [
                node for node in possible_connections if self.s.topology.G.nodes[node]["type"] == "SATELLITE"
            ]
        
        if not possible_connections:
            return []
        
        # Encontrar o nó mais próximo
        closest_node = None
        min_distance = float('inf')
        for node in possible_connections:
            distance = self.calculate_distance(node, mobile_node)
            if distance < min_distance:
                min_distance = distance
                closest_node = node
        
        return [closest_node] if closest_node else []
