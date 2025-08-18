import pandas as pd
from yafs.distribution import deterministicDistributionStartPoint

class UserMobility:
    """
    UserMobility manages the dynamic placement of mobile users (e.g., vehicles) 
    in the simulation topology over time using mobility data from a CSV file.

    The CSV file can be generated with SUMO (Simulation of Urban MObility) or any other source,
    as long as it includes the required columns with the exact names:
        - 'timestep_time': Simulation time for each step.
        - 'vehicle_id': Unique identifier of the vehicle.
        - 'vehicle_x': X-coordinate of the vehicle's position.
        - 'vehicle_y': Y-coordinate of the vehicle's position.

    Attributes:
        sim (Simulation): The simulation object containing the topology.
        csv_file (str): Path to the CSV file with movement data.
        ipt (float): Instructions per time unit (IPT) for the mobile nodes.
        ram (int): RAM size to be assigned to the mobile nodes.
    """
    def __init__(self, sim, csv_file, ipt, ram):
        self.df = pd.read_csv(csv_file, delimiter=';')
        
        self.df = self.df[self.df['timestep_time'] % 60 == 0]
        self.s = sim
        self.topology = sim.topology  
        self.users = {} #Mapping of vehicle IDs to node IDs in the topology
        self.timesteps = sorted(self.df['timestep_time'].unique())
        self.num_timesteps = len(self.timesteps) 
        self.current_timestep = 0
        self.ipt=ipt
        self.ram=ram
        
    def get_next_activation(self):
        """
        Determines the time interval until the next timestep activation.

        Returns:
            int or None: Time difference to the next timestep, or None if simulation has ended.
        """
        if self.current_timestep == 0:
            self.current_timestep += 1
            return 0
        elif self.current_timestep < self.num_timesteps - 1:
            self.current_timestep += 1
            return self.timesteps[self.current_timestep] - self.timesteps[self.current_timestep - 1] 
        else:
            return None

    def update_pos(self, timestep):
        """
        Updates the positions of the mobile nodes in the topology at a given timestep.

        Args:
            timestep (int): The timestep at which to update positions.

        Effects:
            - Adds new nodes to the topology if they appear in the current timestep.
            - Removes nodes that are no longer present in the current timestep.
            - Updates positions of existing nodes.
        """
        current_data = self.df[self.df['timestep_time'] == timestep]

        active_user_m = set(current_data['vehicle_id']) | set(current_data['person_id'])
        
        # Remove outdated from the topology
        for user_m_id in list(self.users.keys()):
            if user_m_id not in active_user_m:
                node_id = self.users.pop(user_m_id)  
                self.s.mobile_users.remove(node_id)
                if node_id in self.topology.G.nodes:
                    self.s.remove_node(node_id)
                    #edges_to_remove = list(self.s.topology.G.edges(node_id))
                    #self.s.topology.G.remove_edges_from(edges_to_remove)
                    #self.topology.G.remove_node(node_id) 

        # Add or update current positions
        for _, row in current_data.iterrows():
    
            if pd.notna(row['vehicle_id']):
                user_m_id = str(row['vehicle_id'])
                user_x = row['vehicle_y']
                user_y = row['vehicle_x']
            else:
                user_m_id = str(row['person_id'])
                user_x = row['person_y']
                user_y = row['person_x']

            if user_m_id in self.users and self.users[user_m_id] in self.topology.G.nodes:
                self.topology.G.nodes[self.users[user_m_id]]['pos'] = (user_x, user_y)
            else:
                self.topology.G.add_node(user_m_id, type="MOBILE", IPT= self.ipt, RAM=self.ram)
                self.s.mobile_users.append(user_m_id)
                self.topology.G.nodes[user_m_id]['pos'] = (user_x, user_y)
                self.users[user_m_id] = user_m_id 
    
    def run(self):
        
        self.update_pos(self.timesteps[self.current_timestep - 1])
        print(f"Timestep {self.timesteps[self.current_timestep - 1]}: {self.s.mobile_users}")
