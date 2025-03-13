import pandas as pd

class UserMobility:
    def __init__(self, sim, csv_file):
        self.df = pd.read_csv(csv_file, delimiter=';')
        self.topology = sim.topology  
        self.users = {}  # Dicionário para armazenar veículos e seus nós na topologia
        self.timesteps = sorted(self.df['timestep_time'].unique())
        self.num_timesteps = len(self.timesteps)
        self.current_timestep = 0
        
    def get_next_activation(self):
        """Calcula o próximo tempo de ativação (timestep) para os veículos. 
        Retorna o próximo timestep ou um valor de tempo aleatório baseado na distribuição."""
        if self.current_timestep == 0:
            self.current_timestep += 1
            return 0
        elif self.current_timestep < self.num_timesteps - 1:
            # Incrementa o timestep para o próximo
            self.current_timestep += 1
            return self.timesteps[self.current_timestep] - self.timesteps[self.current_timestep - 1] 
        else:
            # Se atingiu o último timestep, pode retornar None ou um valor que indique que a simulação terminou
            return None

    def update_pos(self, timestep):
        """Atualiza ou adiciona veículos na topologia conforme o timestep."""
        current_data = self.df[self.df['timestep_time'] == timestep]

        for _, row in current_data.iterrows():
            vehicle_id = str(row['vehicle_id'])  # YAFS usa string como identificador de nó
            vehicle_x = row['vehicle_x']
            vehicle_y = row['vehicle_y']

            if vehicle_id in self.users:
                # Atualiza a posição do veículo na topologia
                self.topology.G.nodes[self.users[vehicle_id]]['pos'] = (vehicle_x, vehicle_y)
            else:
                # Adiciona novo veículo na topologia
                node_id = len(self.topology.G.nodes) + 1  # Gerando um novo ID de nó
                self.topology.G.add_node(node_id, type="MOBILE", IPT= 1, RAM=10)
                self.topology.G.nodes[node_id]['pos'] = (vehicle_x, vehicle_y)
                self.users[vehicle_id] = node_id  # Mapeia o ID do veículo ao nó criado

    def run(self):
        
        self.update_pos(self.timesteps[self.current_timestep - 1])
        #for node, data in self.topology.G.nodes(data=True):
        #    print(f"Nó: {node}")
        #    print(f"Atributos: {data}")
        #    print("-" * 30)
        print(f"Timestep {self.timesteps[self.current_timestep - 1]}: {self.users}")
