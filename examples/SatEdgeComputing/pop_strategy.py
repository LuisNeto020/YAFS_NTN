from yafs.population import Population
from yafs.distribution import Distribution, deterministic_distribution
import random
import numpy as np


class PoissonDistribution(Distribution):
    def __init__(self, name, lam, init_time=0, seed=42):
        super(PoissonDistribution, self).__init__(name)
        self.lam = lam
        self.current_time = init_time
        self.rng = np.random.default_rng(seed)  # Cria um novo Generator

    def next(self):
        interval = self.rng.poisson(self.lam)  # Usa Generator em vez da função legacy
        self.current_time += interval
        return self.current_time

class MISTPopulation(Population):
    def __init__(self, init_time, **kwargs):
        super(MISTPopulation, self).__init__(**kwargs)
        self.app_configs = {
            "AUGMENTED_REALITY": {
                "lambda": 40,
                "message_name": "user_request"
            },
            "E_HEALTH": {
                "lambda": 30,
                "message_name": "user_request"
            },
            "HEAVY_COMP_APP": {
                "lambda": 10,
                "message_name": "user_request"
            }
        }
        self.init_time = init_time
        self.assigned_nodes = []

    def initial_allocation(self, sim, app_name):
        return super().initial_allocation(sim, app_name)

    def run(self, sim):
        for node in sim.topology.G.nodes:
            if sim.topology.G.nodes[node].get("constellation_name") == "mist_synthetic":

                # Escolher aleatoriamente uma aplicação
                app_name = random.choice(list(self.app_configs.keys()))
                app_config = self.app_configs[app_name]
                msg = sim.apps[app_name].get_message(app_config["message_name"])

                # Criar distribuição de Poisson com lambda da app
                dist = PoissonDistribution(name="poissondist", lam=app_config["lambda"], init_time=self.init_time)
                #dist = deterministic_distribution(10, name="deterministic_dist_pop")

                # Registrar fonte de geração de mensagens
                
                sim.deploy_source(app_name, id_node=node, msg=msg, distribution=dist)
                sim.deploy_source(app_name, id_node=node, msg=msg, distribution=dist)

                
            



