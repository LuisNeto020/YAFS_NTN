from yafs.satellite_mobility import SatelliteMobility
from yafs.topology import Topology
from yafs.isl_manager import WalkerLikeISLManager
from yafs.core import Sim
from yafs.selection import First_ShortestPath, OneRandomPath
import networkx as nx
import json
from yafs.distribution import deterministicDistributionStartPoint, Distribution
import time
from yafs.application import create_applications_from_json
from placement_strategy import StaticPlacementMistCloud
from pop_strategy import MISTPopulation
from yafs.path_routing import DeviceSpeedAwareRouting
import logging.config
from pathlib import Path
import matplotlib.pyplot as plt
from Orchestration_algorithms.Round_robin_selection import RoundRobinSelection
from Orchestration_algorithms.Trade_off_selection import TradeOffSelection
from Orchestration_algorithms.Tradi_polling_selection import TradiPollingSelection
from Orchestration_algorithms.Weight_greedy_selection import WeightGreedySelection
from SatEdgeSim_EnergyModel import DefaultEnergyModel
from ISL_All import EnhancedISLManager



class OneTimeDistribution(Distribution):
    def __init__(self, name="one_time_dist", init_time=0):
        super().__init__(name)
        self.init_time = init_time
        self.called = False

    def next(self):
        if not self.called:
            self.called = True
            return self.init_time
        else:
            return float("inf")  # Nunca mais executa


def run_simulation(folder_results, selector_class):
    energy_model = DefaultEnergyModel()
    t = Topology(energy_model=energy_model)
    t.G =  nx.Graph()
    
    s = Sim(t, default_results_path=folder_results + "/sim_trace")
    
    data = json.load(open("data/satelites.json"))
    sat = SatelliteMobility(s, data, r"C:\Users\WRT511\OneDrive\Curso\YAFS_NTN\examples\SatEdgeComputing\data\sat_data.csv")
    dados = sat.use_all_sat()
    s.deploy_satellite_mobility(sat)
    
    """
    APPLICATION or SERVICES
    """
    dataApp = json.load(open('data/appDefinition.json'))
    apps = create_applications_from_json(dataApp)
    for app in apps:
        print(apps[app])
        print(apps[app].messages)
    
    
    placement = StaticPlacementMistCloud(name="Placement")
    
    dist = OneTimeDistribution(init_time=0, name= "onetime")
    population = MISTPopulation(name="population", activation_dist=dist, init_time = 0)
    
    
    dist1 = deterministicDistributionStartPoint(1, 90, name="Deterministic1")
    isl = WalkerLikeISLManager(s, bw=100, time_unit='s', activation_dist=dist1)
    selectorPath = selector_class(isl)
    s.deploy_isl_manager(isl, selectorPath=selectorPath)
    
    
    #selectorPath = DeviceSpeedAwareRouting()
    
    for idx, aName in enumerate(apps.keys()):
        if idx == 0:
            s.deploy_app2(apps[aName], placement, population, selectorPath)
        else:
            s.deploy_app(apps[aName], placement, selectorPath)
      
    

    #print(dados.head())
    #dados.to_csv('meus_dados_v1.csv', index=False)
    """

    RUNNING - last step
    """
    s.run(600)  # To test deployments put test_initial_deploy a TRUE
    s.print_debug_assignaments()
    #nx.draw(t.G, with_labels=True)
    #plt.show()
    
    
LOGGING_CONFIG = Path(__file__).parent / 'logging.ini'
logging.config.fileConfig(LOGGING_CONFIG)

algorithms = {
    "round_robin": RoundRobinSelection,
    "trade_off": TradeOffSelection,
    "tradi_polling": TradiPollingSelection,
    "weight_greedy": WeightGreedySelection
}
#

    
for algo_name, algo_class in algorithms.items():
    for i in range(3, 30):
        print(f"Executando {algo_name} - Simulação {i+1}/...")
        output_dir = Path(f"D:/YAFS_results/Test_SatEdgeSimmm/results/{algo_name}/900/test_{i+1}")
        output_dir.mkdir(parents=True, exist_ok=True)
        run_simulation(str(output_dir), algo_class)
    


print("Finalizado. Resultados guardados em 'resultados_simulacao.txt'.")