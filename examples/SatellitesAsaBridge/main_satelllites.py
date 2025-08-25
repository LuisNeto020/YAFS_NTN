from yafs.satellite_mobility import SatelliteMobility
from yafs.topology import Topology
from yafs.isl_manager import WalkerLikeISLManager
from yafs.core import Sim
from yafs.selection import First_ShortestPath, OneRandomPath
import networkx as nx
import json
from yafs.distribution import deterministicDistributionStartPoint, deterministic_distribution
import time
from yafs.application import create_applications_from_json
from yafs.path_routing import DeviceSpeedAwareRouting
import logging.config
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.pyplot as plt
import contextily as ctx
import geopandas as gpd
from shapely.geometry import Point
import shapely.affinity
import math
from placements.placement_sats import CloudCentricPlacement
from populations.population_sats import EvolPop
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
    gdf_towers.plot(ax=ax, color="red", markersize=30, label="Communication towers")
    '''
    for node in towers:
        node_id = node["id"]
        point = node["geometry"]
        ax.text(point.x, point.y - 0.002, node_id, fontsize=7, ha="center", color="black")
    '''
    for u, v in topology.G.edges():
        if topology.G.nodes[u].get("type") == "STATIC" and topology.G.nodes[v].get("type") == "STATIC":
            lat1, lon1 = topology.G.nodes[u]["pos"]
            lat2, lon2 = topology.G.nodes[v]["pos"]
            ax.plot([lon1, lon2], [lat1, lat2], color="black", linewidth=1, alpha=0.5)

    if map_bounds:
        ax.set_xlim(map_bounds["min_lon"], map_bounds["max_lon"])
        ax.set_ylim(map_bounds["min_lat"], map_bounds["max_lat"])

    ctx.add_basemap(ax, crs="EPSG:4326", source=ctx.providers.OpenStreetMap.Mapnik)

    ax.set_title("Communication towers with 5 km coverage")
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_file)
    plt.show()






def run_simulation(folder_results):
    
    t = Topology()
    t.G =  nx.Graph()
    
    
    t.G.add_node("cloud", type="CLOUD", pos=(48.585562, 7.797538), IPT=250000, RAM=1000000)
    t.G.add_node("cloud1", type="CLOUD", pos=(48.585562, 7.797538), IPT=250000, RAM=1000000)
    t.G.add_node("cloud2", type="CLOUD", pos=(48.585562, 7.797538), IPT=250000, RAM=1000000)
    t.G.add_node("cloud3", type="CLOUD", pos=(48.585562, 7.797538), IPT=250000, RAM=1000000)
    t.G.add_node("cloud4", type="CLOUD", pos=(48.585562, 7.797538), IPT=250000, RAM=1000000)
    
    
    t.G.add_node("emergency_time", type="EMERGENCY_TIME", pos=(41.721214, -7.978884), IPT=10000, RAM=8000)
    t.G.add_node("emergency_time1", type="EMERGENCY_TIME", pos=(41.721214, -7.978884), IPT=10000, RAM=8000)
    t.G.add_node("emergency_time2", type="EMERGENCY_TIME", pos=(41.721214, -7.978884), IPT=10000, RAM=8000)
    
    
    
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
    sat = SatelliteMobility(s, data, r"C:\Users\WRT511\OneDrive\Curso\YAFS_NTN\examples\SatellitesAsaBridge\data\sat_data.csv")
    dados = sat.initial_sat_info()
    s.deploy_satellite_mobility(sat)
    
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
    
    
    selectorPath = DeviceSpeedAwareRouting()
    
    dist1 = deterministic_distribution(60, name="Deterministic1")
    isl = WalkerLikeISLManager(s, bw=1000, time_unit='s', activation_dist=dist1)
    #selectorPath = selector_class(isl)
    s.deploy_isl_manager(isl)
    
    
    #selectorPath = DeviceSpeedAwareRouting()
    
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
        "min_lon": -8.329739,
        "max_lon": -7.864646,
        "min_lat": 41.642532,
        "max_lat": 41.829652
    })
    """
    s.run(3600)  # To test deployments put test_initial_deploy a TRUE
    s.print_debug_assignaments()
    nx.draw(t.G, with_labels=True)
    plt.show()
    
    
#LOGGING_CONFIG = Path(__file__).parent / 'logging.ini'
#logging.config.fileConfig(LOGGING_CONFIG)


for i in range(1):
    print(f"Executando - Simulação {i+1}/...")
    output_dir = Path(f"D:/YAFS_results/Test_SatellitesAsaaBridge/results/hybrid/test_{i+1}")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_simulation(str(output_dir))



print("Finalizado. Resultados guardados em 'resultados_simulacao.txt'.")


