from yafs.population import Population
from yafs.distribution import exponential_distribution

class EvolPop(Population):
    
    def __init__(self,**kwargs):
        super(EvolPop, self).__init__(**kwargs)
        self.user_active = []
        self.pop_deployments = {}
        
    def initial_allocation(self, sim, app_name):
        return super().initial_allocation(sim, app_name)

    def run(self, sim):
        
        new_users = set(sim.mobile_users) - set(self.user_active)
        for user in new_users:
            if sim.topology.G.nodes[user]["type"] == "MOBILE":
                self.user_active.append(user)
                app = sim.apps["EMERGENCY_APP"]
                services = app.services 
                msg = app.get_message("sensor_data")
                #user_des = sim.deploy_module("EMERGENCY_APP", "UserDevice_Module", services["UserDevice_Module"],[user])
                #self.deployments[user] = user_des
                des = sim.deploy_source("EMERGENCY_APP", id_node=user, msg=msg,distribution=exponential_distribution(lambd=120, name="MessageDistri"))
                self.pop_deployments[user] = des
                 
        exit_users = set(self.user_active) - set(sim.mobile_users)
        for ex_user in exit_users:
            #sim.undeploy_module("EMERGENCY_APP", "UserDevice_Module", [self.deployments.get(ex_user)])
            #sim.undeploy_source(self.pop_deployments.get(ex_user))
            self.user_active.remove(ex_user)  
        print(f"exit_users {sim.env.now}: {exit_users} ") 
        #sim.print_debug_assignaments()
        '''
        for node in sim.topology.G.nodes:
            if sim.topology.G.nodes[node]["type"] == "SATELLITE":
                #self.user_active.append(user)
                app = sim.apps["EMERGENCY_APP"]
                services = app.services 
                msg = app.get_message("sensor_data")
                #user_des = sim.deploy_module("EMERGENCY_APP", "UserDevice_Module", services["UserDevice_Module"],[user])
                #self.deployments[user] = user_des
                des = sim.deploy_source("EMERGENCY_APP", id_node=node, msg=msg,distribution=exponential_distribution(lambd=120, name="MessageDistri"))
                 
        '''    



