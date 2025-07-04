from threading import Lock
from yafs.topology import EnergyModel
import math

class DefaultEnergyModel(EnergyModel):
    TRANSMISSION = 0
    RECEPTION = 1

    # Constantes de energia (ajuste com base no seu modelo real)
    E_elec = 0.00000005  # J/bit
    E_fs = 0.00000000001   # J/bit/m^2
    E_mp = 0.0000000000000013  # J/bit/m^4

    def __init__(self):
        super().__init__()
        self.locks = {}  # Um lock por nó

    def _init_node_lock(self, node):
        if node not in self.locks:
            self.locks[node] = Lock()

    def update_cpu_energy_consumption(self, topology, node, time_now, duration_secs):
        self._init_node_lock(node)

        duration_secs = duration_secs.total_seconds()
        now = time_now
        interval_start = now - duration_secs

        G = topology.G
        att_node = G.nodes[node]

        # Inicialmente assume-se sem uso de CPU
        time_active = 0.0
        maxActiveConsumption = att_node.get("maxIdleConsumption", None)
        maxIdleConsumption = att_node.get("maxActiveConsumption", None)
        cpu_state = att_node.get("cpu_util", None)
        if cpu_state:
            utilization, start_time, end_time = cpu_state
            # Calcula interseção entre [start_time, end_time] e [interval_start, now]
            overlap_start = max(start_time, interval_start)
            overlap_end = min(end_time, now)
            time_active = max(0.0, overlap_end - overlap_start)

        cpu_util = time_active / duration_secs

        # Cálculo do consumo de energia (Wh)
        energy_wh = ((maxIdleConsumption +
                    (maxActiveConsumption - maxIdleConsumption) * cpu_util)
                    / 3600.0) * duration_secs

        with self.locks[node]:
            if "ENERGY" not in att_node:
                att_node["ENERGY"] = 0.0
            att_node["ENERGY"] += energy_wh

    def update_wireless_energy_consumption(self, topology, node_src, node_dst, size_bytes, mode):
        """
        Args:
            node (int): ID do nó que envia ou recebe.
            size_kb (float): Tamanho do arquivo em KB.
            distance (float): Distância entre os nós.
            mode (int): TRANSMISSION (0) ou RECEPTION (1)
        """
        if mode == self.TRANSMISSION:
            node = node_src
            distance = self.get_distance(topology, node_src, node_dst)* 1000  
            
        elif mode == self.RECEPTION:
            node = node_dst
            distance = None
            
        self._init_node_lock(node)
        size_bits = size_bytes * 8  # bytes -> bits

        if mode == self.RECEPTION:
            energy_joules = self.E_elec * size_bits
        else:
            D_0 = math.sqrt(self.E_fs / self.E_mp)
            if distance <= D_0:
                energy_joules = (self.E_elec * size_bits) + (self.E_fs * (distance ** 2) * size_bits)
            else:
                energy_joules = (self.E_elec * size_bits) + (self.E_mp * (distance ** 4) * size_bits)

        energy_wh = energy_joules / 3600.0

        with self.locks[node]:
            G = self.sim.topology.G
            if "ENERGY" not in G.nodes[node]:
                G.nodes[node]["ENERGY"] = 0.0
            G.nodes[node]["ENERGY"] += energy_wh
            
    def get_distance(self, topology, sat_u, sat_v):
        """
        Computes the Euclidean distance between two satellites in spherical coordinates.
        Equation based on provided LoS-aware model.
        """
        try:
            lat_u, lon_u = topology.G.nodes[sat_u]['sub_pos']
            lat_v, lon_v = topology.G.nodes[sat_v]['sub_pos']
            
            r1 = 6371 + topology.G.nodes[sat_u]['altitude']
            r2 = 6371 + topology.G.nodes[sat_v]['altitude']

            theta_u = math.pi / 2 - math.radians(lat_u) 
            theta_v = math.pi / 2 - math.radians(lat_v) 
            epsilon_p = math.radians(lon_u)
            epsilon_q = math.radians(lon_v)

            cos_term = (
                math.cos(theta_u) * math.cos(theta_v) +
                math.cos(epsilon_p - epsilon_q) * math.sin(theta_u) * math.sin(theta_v)
            )

            distance = math.sqrt(r1**2 + r2**2 - 2 * r1 * r2 * cos_term)
            return distance
        except KeyError:
            return float('inf')
