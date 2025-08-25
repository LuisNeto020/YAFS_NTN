from yafs.placement import Placement

class CloudCentricPlacement(Placement):
    def __init__(self, **kwargs):
        super(CloudCentricPlacement, self).__init__(**kwargs)
        self.user_active = []
        self.plc_deployments = {}

    def initial_allocation(self, sim, app_name):
        """
        Aloca o módulo de storage na cloud no início da simulação.
        """
        app = sim.apps["EMERGENCY_APP"]
        services = app.services
        
        for node_id, data in sim.topology.G.nodes(data=True):
            if data.get("type") == "CLOUD":
                sim.deploy_module("EMERGENCY_APP", "Cloud_Module", services["Cloud_Module"],[node_id])
                sim.deploy_module("EMERGENCY_APP", "Cloud_Module", services["Cloud_Module"],[node_id])
                sim.deploy_module("EMERGENCY_APP", "Cloud_Module", services["Cloud_Module"],[node_id])
                sim.deploy_module("EMERGENCY_APP", "Cloud_Module", services["Cloud_Module"],[node_id])
                
            if data.get("type") == "EMERGENCY_TIME":
                 sim.deploy_module("EMERGENCY_APP", "Emergency_Service_Module", services["Emergency_Service_Module"],[node_id])
                 sim.deploy_module("EMERGENCY_APP", "Emergency_Service_Module", services["Emergency_Service_Module"],[node_id])
                 
        for node_id in sim.static_nodes:
            if sim.topology.G.nodes[node_id]["type"] == "CLOUD" or sim.topology.G.nodes[node_id]["type"] == "EMERGENCY_TIME":
                continue
            sim.deploy_module("EMERGENCY_APP", "UserDevice_Module", services["UserDevice_Module"],[node_id])
           