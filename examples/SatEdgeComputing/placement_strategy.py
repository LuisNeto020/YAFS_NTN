from yafs.placement import Placement


class StaticPlacementMistCloud(Placement):
    def __init__(self, **kwargs):
        super(StaticPlacementMistCloud, self).__init__(**kwargs)

    def initial_allocation(self, sim, app_name):
        
        app = sim.apps[app_name]
        services = app.services

        # Aloca cliente em todos os nós mist
        mist_nodes = [node for node in sim.topology.G.nodes
                      if sim.topology.G.nodes[node].get("constellation_name") == "mist_synthetic"]
        print(f"aquiiiiii ->>>>>{sim.topology.G.nodes}")
        for node in mist_nodes:
            sim.deploy_module(app_name, "Client_Module", services["Client_Module"], [node])

        # Aloca processamento em um único nó Cloud
        
        
        cloud_nodes = [node for node in sim.topology.G.nodes]
        
        #if cloud_nodes:
            # Seleciona o primeiro nó como o nó de processamento
           # processing_node = cloud_nodes[0]
           # sim.deploy_module(app_name, "Processing_Module", services["Processing_Module"], [processing_node])
        
        for cloud_node in cloud_nodes:
            sim.deploy_module(app_name, "Processing_Module", services["Processing_Module"], [cloud_node])
        
