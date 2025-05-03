import pandas as pd
from yafs.distribution import deterministicDistributionStartPoint

class UserMobility:
    def __init__(self, sim, csv_file):
        self.df = pd.read_csv(csv_file, delimiter=';')
        self.s = sim
        self.topology = sim.topology  
        self.users = {}  # Dicionário para armazenar veículos e seus nós na topologia
        self.users_des = {} 
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

        # Primeiro, verifique todos os veículos que estão na topologia
        active_vehicles = set(current_data['vehicle_id'])
        
         # Remover nós de veículos que não estão no timestep atual
        for vehicle_id in list(self.users.keys()):
            if vehicle_id not in active_vehicles:
                node_id = self.users.pop(vehicle_id)  # Remove o veículo do dicionário
                self.s.mobile_users.remove(node_id)
                #self.s.undeploy_module("ats", "Client_Module", node_id)
                #self.users_des.pop(vehicle_id)
                if node_id in self.topology.G.nodes:
                    print("no removido",node_id)
                    edges_to_remove = list(self.s.topology.G.edges(node_id))
                    # Remove todas as arestas
                    self.s.topology.G.remove_edges_from(edges_to_remove)
                    self.topology.G.remove_node(node_id)  # Remove o nó da topologia

        
        for _, row in current_data.iterrows():
            vehicle_id = str(row['vehicle_id'])  # YAFS usa string como identificador de nó
            vehicle_x = row['vehicle_y']
            vehicle_y = row['vehicle_x']

            if vehicle_id in self.users and self.users[vehicle_id] in self.topology.G.nodes:
                # Atualiza a posição do veículo na topologia
                self.topology.G.nodes[self.users[vehicle_id]]['pos'] = (vehicle_x, vehicle_y)
            else:
                # Adiciona novo veículo na topologia
                self.topology.G.add_node(vehicle_id, type="MOBILE", IPT= 500, RAM=1000)
                self.s.mobile_users.append(vehicle_id)
                self.topology.G.nodes[vehicle_id]['pos'] = (vehicle_x, vehicle_y)
                #app = self.s.apps["ats"]
                #msg = app.get_message("m-sensor")
                #des = self.s.deploy_source("ats", id_node=vehicle_id, msg=msg,distribution=deterministicDistributionStartPoint(0.9999, 1, name="MessageDistri"))
                #app = self.s.apps["ats"]
                #services = app.services
                #self.s.deploy_module("ats", "Client_Module", services["Client_Module"],[vehicle_id])
                self.users[vehicle_id] = vehicle_id  # Mapeia o ID do veículo ao nó criado
                #self.users_des[vehicle_id] = des

    def run(self):
        
        self.update_pos(self.timesteps[self.current_timestep - 1])
        #for node, data in self.topology.G.nodes(data=True):
        #    print(f"Nó: {node}")
        #    print(f"Atributos: {data}")
        #    print("-" * 30)
        print(f"Timestep {self.timesteps[self.current_timestep - 1]}: {self.s.mobile_users}")
