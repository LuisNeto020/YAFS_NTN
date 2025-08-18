from yafs.satellite_mobility import SatelliteMobility
from yafs.topology import Topology
from yafs.isl_manager import WalkerLikeISLManager
from yafs.core import Sim
from yafs.selection import First_ShortestPath, OneRandomPath
import networkx as nx
from Weight_greedy_selection import WeightGreedySelection
from Weight_greedy_selection_sat import WeightGreedySelectionSat 
import json
from yafs.distribution import deterministicDistributionStartPoint, deterministic_distribution
import time
from yafs.application import create_applications_from_json
from yafs.path_routing import DeviceSpeedAwareRouting
import logging.config
from pathlib import Path
import matplotlib.pyplot as plt
from oneweb_isl_manager import OnewebISLManager
import matplotlib.pyplot as plt
import contextily as ctx
import geopandas as gpd
from shapely.geometry import Point
import shapely.affinity
import math
from placementAlg import CloudCentricPlacement
from populationAlg import EvolPop
from yafs.user_mobility import UserMobility
from yafs.coverage import CircleCoverage




def degrees_lon_per_km_at_lat(lat):
    """Converte 1 km em graus de longitude em determinada latitude"""
    return 1 / (111.320 * math.cos(math.radians(lat)))


def plot_static_nodes(topology, map_bounds=None, output_file="static_nodes_5km_geo.png"):
    circles = []
    towers = []

    for node_id, data in topology.G.nodes(data=True):
        if data.get("type") == "STATIC" and "pos" in data:
            lat, lon = data["pos"]
            point = Point(lon, lat)
            towers.append({"id": node_id, "geometry": point})

            # Aproximação: 1 grau lat ≈ 111 km
            deg_lat = 6 / 111.0  # 5 km em graus latitude
            deg_lon = degrees_lon_per_km_at_lat(lat) * 6  # 5 km em graus longitude

            # Criar círculo manualmente (elipse para manter proporção correta em graus)
            circle = point.buffer(1)  # buffer unitário (em graus)
            scaled_circle = shapely.affinity.scale(circle, xfact=deg_lon, yfact=deg_lat, origin=point)
            circles.append(scaled_circle)

    # Criar GeoDataFrames
    gdf_towers = gpd.GeoDataFrame(towers, crs="EPSG:4326")
    gdf_buffers = gpd.GeoDataFrame(geometry=circles, crs="EPSG:4326")

    # Plotar
    fig, ax = plt.subplots(figsize=(12, 8))
    gdf_buffers.plot(ax=ax, edgecolor="blue", facecolor="blue", alpha=0.2, label="Cobertura 5 km")
    gdf_towers.plot(ax=ax, color="red", markersize=30, label="Torres Estáticas")
    
    for node in towers:
        node_id = node["id"]
        point = node["geometry"]
        ax.text(point.x, point.y - 0.002, node_id, fontsize=7, ha="center", color="black")
    
    for u, v in topology.G.edges():
        if topology.G.nodes[u].get("type") == "STATIC" and topology.G.nodes[v].get("type") == "STATIC":
            lat1, lon1 = topology.G.nodes[u]["pos"]
            lat2, lon2 = topology.G.nodes[v]["pos"]
            ax.plot([lon1, lon2], [lat1, lat2], color="black", linewidth=1, alpha=0.5)

    if map_bounds:
        ax.set_xlim(map_bounds["min_lon"], map_bounds["max_lon"])
        ax.set_ylim(map_bounds["min_lat"], map_bounds["max_lat"])

    ctx.add_basemap(ax, crs="EPSG:4326", source=ctx.providers.OpenStreetMap.Mapnik)

    ax.set_title("Torres com cobertura de 5 km (geográfica)")
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_file)
    plt.show()






def run_simulation(folder_results):
    
    t = Topology()
    t.G =  nx.Graph()
    
    t.G.add_node("node10762139299", type="STATIC", pos=(41.7803249, -8.2696795), IPT=25000, RAM=8000)
    t.G.add_node("node11609974323", type="STATIC", pos=(41.767395, -8.240963), IPT=25000, RAM=8000)
    t.G.add_node("node10762139300", type="STATIC", pos=(41.7483988, -8.2289958), IPT=25000, RAM=8000)
    t.G.add_node("node9606132852",  type="STATIC", pos=(41.7481369, -8.2005327), IPT=25000, RAM=8000)
    t.G.add_node("node11586863472", type="STATIC", pos=(41.743385, -8.279699), IPT=25000, RAM=8000)
    t.G.add_node("node7302204030",  type="STATIC", pos=(41.7273495, -8.3025206), IPT=25000, RAM=8000)
    t.G.add_node("node10247269222", type="STATIC", pos=(41.6958616, -8.246854), IPT=25000, RAM=8000)
    t.G.add_node("node10767267430", type="STATIC", pos=(41.6582126, -8.3022389), IPT=25000, RAM=8000)
    t.G.add_node("node9677655121",  type="STATIC", pos=(41.6714192, -8.1599611), IPT=25000, RAM=8000)
    t.G.add_node("node12943752612", type="STATIC", pos=(41.6982319, -8.1288032), IPT=25000, RAM=8000)
    t.G.add_node("node9676977102",  type="STATIC", pos=(41.6982919, -8.1005435), IPT=25000, RAM=8000)
    t.G.add_node("node9676977103",  type="STATIC", pos=(41.6833651, -8.0554837), IPT=25000, RAM=8000)
    t.G.add_node("node12191545276", type="STATIC", pos=(41.7149995, -8.0307287), IPT=25000, RAM=8000)
    t.G.add_node("node3810713697",  type="STATIC", pos=(41.6936492, -7.9771511), IPT=25000, RAM=8000)
    t.G.add_node("node9676977104",  type="STATIC", pos=(41.6739596, -8.0024524), IPT=25000, RAM=8000)
    t.G.add_node("node10281233974", type="STATIC", pos=(41.6640746, -7.8994194), IPT=25000, RAM=8000)
    t.G.add_node("node9677461511",  type="STATIC", pos=(41.7427314, -7.8721815), IPT=25000, RAM=8000)
    t.G.add_node("node9631463963",  type="STATIC", pos=(41.7799282, -7.8055146), IPT=25000, RAM=8000)
    t.G.add_node("node10762139303", type="STATIC", pos=(41.8289978, -7.8493854), IPT=25000, RAM=8000)
    t.G.add_node("node9633847528",  type="STATIC", pos=(41.71778, -8.1637729), IPT=25000, RAM=8000)
    t.G.add_node("node9634402357",  type="STATIC", pos=(41.7258847, -8.1646876), IPT=25000, RAM=8000)
    t.G.add_node("node3091549588",  type="STATIC", pos=(41.8129999, -8.1949169), IPT=25000, RAM=8000)
    t.G.add_node("node10082448941", type="STATIC", pos=(41.7495991, -7.9583519), IPT=25000, RAM=8000)
    t.G.add_node("node9499514917",  type="STATIC", pos=(41.7401386, -7.9481038), IPT=25000, RAM=8000)
    t.G.add_node("node10253004472", type="STATIC", pos=(41.8381797, -7.946983), IPT=25000, RAM=8000)
    t.G.add_node("node12583031276", type="STATIC", pos=(41.792778, -7.887053), IPT=25000, RAM=8000)
    
    t.G.add_node("proxy1", type="PROXY", pos=(41.690201, -8.204110), IPT=5000, RAM=16000)
    t.G.add_node("proxy2", type="PROXY", pos=(41.721214, -7.978884), IPT=5000, RAM=16000)
    
    t.G.add_node("cloud", type="CLOUD", pos=(48.585562, 7.797538), IPT=2500000, RAM=1000000)
    t.G.add_node("cloud1", type="CLOUD", pos=(48.585562, 7.797538), IPT=2500000, RAM=1000000)
    t.G.add_node("cloud2", type="CLOUD", pos=(48.585562, 7.797538), IPT=2500000, RAM=1000000)
    t.G.add_node("cloud3", type="CLOUD", pos=(48.585562, 7.797538), IPT=2500000, RAM=1000000)
    t.G.add_node("cloud4", type="CLOUD", pos=(48.585562, 7.797538), IPT=2500000, RAM=1000000)
    
    
    t.G.add_node("emergency_time", type="EMERGENCY_TIME", pos=(41.721214, -7.978884), IPT=25000, RAM=8000)
    t.G.add_node("emergency_time1", type="EMERGENCY_TIME", pos=(41.721214, -7.978884), IPT=25000, RAM=8000)
    t.G.add_node("emergency_time2", type="EMERGENCY_TIME", pos=(41.721214, -7.978884), IPT=25000, RAM=8000)
    
    t.G.add_edge("node10762139299", "node11609974323", BW=1000, PR=0.001)
    t.G.add_edge("node11609974323", "node10762139300", BW=1000, PR=0.001)
    t.G.add_edge("node10762139300", "node9606132852", BW=1000, PR=0.001)
    t.G.add_edge("node9606132852", "node10762139300", BW=1000, PR=0.001)
    t.G.add_edge("node11586863472", "node10762139299", BW=1000, PR=0.001)
    t.G.add_edge("node7302204030", "node11586863472", BW=1000, PR=0.001)
    t.G.add_edge("node10247269222", "node11609974323", BW=1000, PR=0.001)
    t.G.add_edge("node10767267430", "node7302204030", BW=1000, PR=0.001)
    t.G.add_edge("node9677655121", "node12943752612", BW=1000, PR=0.001)
    t.G.add_edge("node12943752612", "node9677655121", BW=1000, PR=0.001)
    t.G.add_edge("node9676977102", "node12943752612", BW=1000, PR=0.001)
    t.G.add_edge("node9676977103", "node9676977102", BW=1000, PR=0.001)
    t.G.add_edge("node12191545276", "node9676977103", BW=1000, PR=0.001)
    t.G.add_edge("node3810713697", "node12191545276", BW=1000, PR=0.001)
    t.G.add_edge("node9676977104", "node3810713697", BW=1000, PR=0.001)
    t.G.add_edge("node10281233974", "node9676977104", BW=1000, PR=0.001)
    t.G.add_edge("node9677461511", "node10281233974", BW=1000, PR=0.001)
    t.G.add_edge("node9631463963", "node9677461511", BW=1000, PR=0.001)
    t.G.add_edge("node10762139303", "node9631463963", BW=1000, PR=0.001)
    t.G.add_edge("node9633847528", "node9634402357", BW=1000, PR=0.001)
    t.G.add_edge("node9634402357", "node9633847528", BW=1000, PR=0.001)
    t.G.add_edge("node3091549588", "node10762139299", BW=1000, PR=0.001)
    t.G.add_edge("node10082448941", "node9499514917", BW=1000, PR=0.001)
    t.G.add_edge("node9499514917", "node10082448941", BW=1000, PR=0.001)
    t.G.add_edge("node10253004472", "node10762139303", BW=1000, PR=0.001)
    t.G.add_edge("node12583031276", "node10253004472", BW=1000, PR=0.001)
    t.G.add_edge("node9606132852", "node9634402357", BW=1000, PR=0.001)
    t.G.add_edge("node9606132852", "node10247269222", BW=1000, PR=0.001)
    t.G.add_edge("node9633847528", "node9677655121", BW=1000, PR=0.001)
    t.G.add_edge("node9633847528", "node12943752612", BW=1000, PR=0.001)
    t.G.add_edge("node12583031276", "node10082448941", BW=1000, PR=0.001)
    t.G.add_edge("node3810713697", "node9499514917", BW=1000, PR=0.001)
    
    t.G.add_edge("node10247269222", "proxy1", BW=1000, PR=0.004)
    t.G.add_edge("node9677655121", "proxy1", BW=1000, PR=0.004)
    t.G.add_edge("node12191545276", "proxy2", BW=1000, PR=0.004)
    t.G.add_edge("node10082448941", "proxy2", BW=1000, PR=0.004)
    
    t.G.add_edge("cloud", "proxy1", BW=1000, PR=0.090)
    t.G.add_edge("cloud", "proxy2", BW=1000, PR=0.090)
    t.G.add_edge("cloud1", "proxy1", BW=1000, PR=0.090)
    t.G.add_edge("cloud1", "proxy2", BW=1000, PR=0.090)
    t.G.add_edge("cloud2", "proxy1", BW=1000, PR=0.090)
    t.G.add_edge("cloud2", "proxy2", BW=1000, PR=0.090)
    t.G.add_edge("cloud3", "proxy1", BW=1000, PR=0.090)
    t.G.add_edge("cloud3", "proxy2", BW=1000, PR=0.090)
    t.G.add_edge("cloud4", "proxy1", BW=1000, PR=0.090)
    t.G.add_edge("cloud4", "proxy2", BW=1000, PR=0.090)
    
    t.G.add_edge("emergency_time", "node9676977104", BW=300, PR=0.001)
    t.G.add_edge("emergency_time1", "node3810713697", BW=300, PR=0.001)
    t.G.add_edge("emergency_time2", "node10281233974", BW=300, PR=0.001)
    
    
    
    #t.G.add_edge("cloud", "ONEWEB-0253", BW=1000, PR=0.001)
    #t.G.add_edge("emergency_time", "ONEWEB-0254", BW=1000, PR=0.001)

    s = Sim(t, default_results_path=folder_results + "/sim_trace")
    s.mobile_users.append("cloud")
    s.mobile_users.append("cloud1")
    s.mobile_users.append("cloud2")
    s.mobile_users.append("cloud3")
    s.mobile_users.append("cloud4")
    s.mobile_users.append("emergency_time")
    s.mobile_users.append("emergency_time1")
    s.mobile_users.append("emergency_time2")
    data = json.load(open("data/satelites.json"))
    #sat = SatelliteMobility(s, data, r"C:\Users\WRT511\OneDrive\Curso\YAFS_NTN\examples\SatellitesInFog\data\sat_data.csv")
    #dados = sat.initial_sat_info()
    #s.deploy_satellite_mobility(sat)
    
    """
    APPLICATION or SERVICES
    """
    dataApp = json.load(open('data/appDefinition.json'))
    apps = create_applications_from_json(dataApp)
    for app in apps:
        print(apps[app])

    """ 
    SERVICE PLACEMENT 
    """
    dist_1 = deterministic_distribution(60, name="Deterministic")
    placement = CloudCentricPlacement(name="Placement", activation_dist=dist_1)
    
    dist = deterministic_distribution(60, name="Deterministic")
    population = EvolPop(name="population", activation_dist=dist)
    
    
    #selectorPath = WeightGreedySelection()
    
    dist1 = deterministic_distribution(60, name="Deterministic1")
    isl = WalkerLikeISLManager(s, bw=1000, time_unit='s', activation_dist=dist1)
    #selectorPath = selector_class(isl)
    #s.deploy_isl_manager(isl)
    
    
    selectorPath = DeviceSpeedAwareRouting()
    
    for idx, aName in enumerate(apps.keys()):
        s.deploy_app2(apps[aName], placement, population, selectorPath)
    #    else:
    #        s.deploy_app(apps[aName], placement, selectorPath)
      
    """
    Deploy users
    """ 
    csv_path = r"C:\Users\WRT511\OneDrive\Curso\YAFS_NTN\examples\SatellitesAsaBridge\fcd_output_filtered.csv"   
    u = UserMobility(s, csv_path, 500, 1000)
    s.deploy_user_mobility(u)

    #print(dados.head())
    #dados.to_csv('meus_dados_v1.csv', index=False)
    
    """
    Deploy coverage
    """
    dist = deterministic_distribution(60, name="Deterministic")
    coverage = CircleCoverage(activation_dist=dist, sim=s, radius=4, bw_ter=300, pr_ter=0.002, bw_sat=200, time_unit="s")
    s.deploy_coverage(coverage)
    
    """

    RUNNING - last step
    
    plot_static_nodes(t, map_bounds={
        "min_lon": -8.309739,
        "max_lon": -7.884646,
        "min_lat": 41.662532,
        "max_lat": 41.809652
    })"""
    s.run(3600)  # To test deployments put test_initial_deploy a TRUE
    #s.print_debug_assignaments()
    nx.draw(t.G, with_labels=True)
    plt.show()
    
    
#LOGGING_CONFIG = Path(__file__).parent / 'logging.ini'
#logging.config.fileConfig(LOGGING_CONFIG)


for i in range(1, 3):
    print(f"Executando - Simulação {i+1}/...")
    output_dir = Path(f"D:/YAFS_results/Test_SatellitesInFoggg/results/fog_in_terrestrial_and_satellites_nodes/test_{i+1}")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_simulation(str(output_dir))



print("Finalizado. Resultados guardados em 'resultados_simulacao.txt'.")


