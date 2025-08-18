from datetime import datetime, timedelta
import pandas as pd
import os
import json
from skyfield.api import load, EarthSatellite, Topos, wgs84
from skyfield.iokit import parse_tle_file
from math import cos, radians, asin

class SatelliteMobility:
    
    def __init__(self, sim, json, data_cache_path):
        self.json_data = json
        self.next_timestep = self.json_data["time_interval"]["check_frequency"]
        self.df = None
        self.satellites = {}
        self.modules_alloc_sat = {}
        self.node_atr = {}
        self.consumption_atr = {}
        self.sim = sim
        self.data_cache_path = data_cache_path
        
        
    def get_next_activation(self):
        return self.next_timestep
    
    
    def use_all_sat(self):
        if os.path.exists(self.data_cache_path):
            print(f"Arquivo de cache encontrado em '{self.data_cache_path}'. Carregando...")
            self.df = pd.read_csv(self.data_cache_path)
            ts = load.timescale()
            self.df["time"] = self.df["time"].apply(lambda t: ts.utc(pd.to_datetime(t).to_pydatetime()))
        else:
            ts = load.timescale()
            start_time = datetime.fromisoformat(self.json_data["time_interval"]["start_time"].replace("Z", "+00:00"))
            duration = self.json_data["time_interval"]["duration"]
            duration_unit = self.json_data["time_interval"]["unit"]
            interval_value = self.json_data["time_interval"]["check_frequency"]


            end_time = start_time + self.__parse_interval_unit(duration, duration_unit)
            interval = self.__parse_interval_unit(interval_value, duration_unit)
            #print("tempo final:",end_time)

            min_altitude = self.json_data.get("minimum_altitude_angle", 0.0)

            # 3. Carregar satélites de todas as constelações
            satellites = []
            for constellation in self.json_data["constellations"]:
                satellites += self.__fetch_satellites(constellation, ts)
                
            current_time = start_time
            records = []
                
            timestep = 0
            while current_time <= end_time:
                t = ts.utc(current_time.year, current_time.month, current_time.day,
                        current_time.hour, current_time.minute, current_time.second)

                for sat in satellites:
                    geocentric = sat.at(t)
                    sat_lat, sat_lon = wgs84.latlon_of(geocentric)
                    subpoint = geocentric.subpoint()
                    EARTH_RADIUS_KM = 6371.0

                    # Altura do satélite acima da superfície
                    #sat_alt_km = subpoint.elevation.km
                    sat_alt_km = wgs84.height_of(geocentric).km
                    # Elevação mínima em radianos
                    epsilon_0_rad = radians(min_altitude)
                    
                    # Calcular sin(α0)
                    sin_alpha_0 = (EARTH_RADIUS_KM / (EARTH_RADIUS_KM + sat_alt_km)) * cos(epsilon_0_rad)
                    
                    alpha_0_rad = asin(sin_alpha_0)

                    # Calcular β0
                    beta_0_rad = radians(90) - epsilon_0_rad - alpha_0_rad

                    # Raio da área visível na superfície
                    coverage_radius_km = EARTH_RADIUS_KM * beta_0_rad
    
                    raan = sat.model.nodeo
                    mo = sat.model.mo

                    
                    records.append({
                        "timestep": timestep,
                        "time": t,
                        "satellite_id": sat.name,
                        "constellation_name": getattr(sat, "constellation_name", "Unknown"),
                        "latitude": sat_lat.degrees,
                        "longitude": sat_lon.degrees,
                        "sub_lat": subpoint.latitude.degrees,
                        "sub_lon": subpoint.longitude.degrees,
                        "altitude": subpoint.elevation.km,
                        "coverage_radius_km": coverage_radius_km,
                        "coverage_angle_rad": beta_0_rad,
                        "raan": raan,
                        "mo": mo
                    })

                timestep += interval_value
                current_time += interval
                
                

            self.df = pd.DataFrame(records)
            dtt= pd.DataFrame(records)
            dtt["time"] = dtt["time"].apply(lambda t: t.utc_iso())
            dtt.to_csv(self.data_cache_path, index=False)
        for constellation in self.json_data["constellations"]:
            name = constellation["name"]
            
            # Guardar atributos de nó (IPT, RAM)
            self.node_atr[name] = (
                constellation.get("IPT", 500),
                constellation.get("RAM", 1000)
            )
            
            max_idle = constellation.get("maxIdleConsumption", None)
            max_active = constellation.get("maxActiveConsumption", None)
            
            if max_idle is not None and max_active is not None:
                self.consumption_atr[name] = {
                    "maxIdleConsumption": max_idle,
                    "maxActiveConsumption": max_active
                }
            
        current_data = self.df[self.df['timestep'] == 0]
        
        for _, row in current_data.iterrows():
            sat_id = str(row["satellite_id"])
            constellation = row["constellation_name"]
            x = row["latitude"]
            y = row["longitude"]
            self.sim.topology.G.add_node(sat_id, type="SATELLITE", IPT=self.node_atr[constellation][0], RAM=self.node_atr[constellation][1])
            self.sim.topology.G.nodes[sat_id]['pos'] = (row["sub_lat"], row["sub_lon"])
            self.sim.topology.G.nodes[sat_id]['sub_pos'] = (x,y)
            self.sim.topology.G.nodes[sat_id]["coverage_radius_km"] = row["coverage_radius_km"]
            self.sim.topology.G.nodes[sat_id]["coverage_angle_rad"] = row["coverage_angle_rad"]
            self.sim.topology.G.nodes[sat_id]['time'] = row["time"]
            self.sim.topology.G.nodes[sat_id]['altitude'] = row["altitude"]
            self.sim.topology.G.nodes[sat_id]["raan"] = row["raan"]
            self.sim.topology.G.nodes[sat_id]["mo"] = row["mo"]
            self.sim.topology.G.nodes[sat_id]["constellation_name"] = row["constellation_name"]
            self.sim.static_nodes.append(sat_id)
            if constellation in self.consumption_atr:
                self.sim.topology.G.nodes[sat_id]["maxIdleConsumption"] = self.consumption_atr[constellation]["maxIdleConsumption"]
                self.sim.topology.G.nodes[sat_id]["maxActiveConsumption"] = self.consumption_atr[constellation]["maxActiveConsumption"]

        return self.df
            
            
    def initial_sat_info(self):
        
        if os.path.exists(self.data_cache_path):
            print(f"Arquivo de cache encontrado em '{self.data_cache_path}'. Carregando...")
            self.df = pd.read_csv(self.data_cache_path)
            ts = load.timescale()
            self.df["time"] = self.df["time"].apply(lambda t: ts.utc(pd.to_datetime(t).to_pydatetime()))
        else:
            ts = load.timescale()

            # 1. Obter posição central
            observer_lat = (self.json_data["latitude"]["min"] + self.json_data["latitude"]["max"]) / 2
            observer_lon = (self.json_data["longitude"]["min"] + self.json_data["longitude"]["max"]) / 2
            observer = Topos(latitude_degrees=observer_lat, longitude_degrees=observer_lon)

            # 2. Tempo
            start_time = datetime.fromisoformat(self.json_data["time_interval"]["start_time"].replace("Z", "+00:00"))
            duration = self.json_data["time_interval"]["duration"]
            duration_unit = self.json_data["time_interval"]["unit"]
            interval_value = self.json_data["time_interval"]["check_frequency"]


            end_time = start_time + self.__parse_interval_unit(duration, duration_unit)
            interval = self.__parse_interval_unit(interval_value, duration_unit)
            #print("tempo final:",end_time)

            min_altitude = self.json_data.get("minimum_altitude_angle", 0.0)

            # 3. Carregar satélites de todas as constelações
            satellites = []
            for constellation in self.json_data["constellations"]:
                satellites += self.__fetch_satellites(constellation, ts)
                
            visibility_windows = {}
            for sat in satellites:
                windows = self.__get_visibility_intervals(sat, observer, ts, start_time, end_time, min_altitude)
                visibility_windows[sat.name] = windows
            # 4. Loop temporal
            current_time = start_time
            records = []

            timestep = 0
            while current_time <= end_time:
                t = ts.utc(current_time.year, current_time.month, current_time.day,
                        current_time.hour, current_time.minute, current_time.second)

                for sat in satellites:
                    windows = visibility_windows.get(sat.name, [])
                    if not self.__is_visible(current_time, windows):
                        continue
                    geocentric = sat.at(t)
                    sat_lat, sat_lon = wgs84.latlon_of(geocentric)
                    subpoint = geocentric.subpoint()
                    EARTH_RADIUS_KM = 6371.0

                    # Altura do satélite acima da superfície
                    #sat_alt_km = subpoint.elevation.km
                    sat_alt_km = wgs84.height_of(geocentric).km
                    # Elevação mínima em radianos
                    epsilon_0_rad = radians(min_altitude)
                    
                    # Calcular sin(α0)
                    sin_alpha_0 = (EARTH_RADIUS_KM / (EARTH_RADIUS_KM + sat_alt_km)) * cos(epsilon_0_rad)
                    
                    alpha_0_rad = asin(sin_alpha_0)

                    # Calcular β0
                    beta_0_rad = radians(90) - epsilon_0_rad - alpha_0_rad

                    # Raio da área visível na superfície
                    coverage_radius_km = EARTH_RADIUS_KM * beta_0_rad
                    
                    raan = sat.model.nodeo
                    mo = sat.model.mo

                    
                    records.append({
                        "timestep": timestep,
                        "time": t,
                        "satellite_id": sat.name,
                        "constellation_name": getattr(sat, "constellation_name", "Unknown"),
                        "latitude": sat_lat.degrees,
                        "longitude": sat_lon.degrees,
                        "sub_lat": subpoint.latitude.degrees,
                        "sub_lon": subpoint.longitude.degrees,
                        "altitude": subpoint.elevation.km,
                        "coverage_radius_km": coverage_radius_km,
                        "coverage_angle_rad": beta_0_rad,
                        "raan": raan,
                        "mo": mo
                    })

                timestep += interval_value
                current_time += interval
                #print("timestep---->",timestep )
                

            self.df = pd.DataFrame(records)
            dtt= pd.DataFrame(records)
            dtt["time"] = dtt["time"].apply(lambda t: t.utc_iso())
            dtt.to_csv(self.data_cache_path, index=False)
        for constellation in self.json_data["constellations"]:
            name = constellation["name"]
            
            # Guardar módulos dessa constelação
            self.modules_alloc_sat[name] = []
            for module in constellation.get("modules", []):
                app = module["app"]
                mod = module["module"]
                self.modules_alloc_sat[name].append((app, mod))
            
            # Guardar atributos de nó (IPT, RAM)
            self.node_atr[name] = (
                constellation.get("IPT", 500),
                constellation.get("RAM", 1000)
            )
            
        print(self.df.head())
        return self.df
    
    def __get_visibility_intervals(self, satellite, observer, ts, start_time, end_time, min_altitude=0.0):
        """Encontra intervalos de visibilidade do satélite, incluindo casos limítrofes."""
        t0 = ts.utc(start_time.year, start_time.month, start_time.day,
                    start_time.hour, start_time.minute, start_time.second)
        t1 = ts.utc(end_time.year, end_time.month, end_time.day,
                    end_time.hour, end_time.minute, end_time.second)

        t_events, events = satellite.find_events(observer, t0, t1, altitude_degrees=min_altitude)
        visibility_windows = []
        current_window = None

        # Se o primeiro evento for set (2) ou culminação (1), já estava visível
        if len(events) > 0 and events[0] in [1, 2]:
            current_window = {"start": start_time}

        for ti, event in zip(t_events, events):
            if event == 0:  # Rise
                current_window = {"start": ti.utc_datetime()}
            elif event == 2 and current_window:  # Set
                current_window["end"] = ti.utc_datetime()
                visibility_windows.append(current_window)
                current_window = None

        # Se ainda estiver visível no fim do período
        if current_window:
            current_window["end"] = end_time
            visibility_windows.append(current_window)
            
        if len(events) == 0:
            alt, az, distance = (satellite-observer).at(t0).altaz()
            if alt.degrees >= min_altitude:
                visibility_windows.append({"start": start_time, "end": end_time})
        return visibility_windows


    def __is_visible(self, current_time, windows):
        """Checa se current_time está dentro de alguma janela de visibilidade."""
        for window in windows:
            if window["start"] <= current_time <= window["end"]:
                return True
        return False

        
    def update_satellite_positions(self, timestep):
        """Atualiza ou adiciona satélites na topologia conforme o timestep."""
        current_data = self.df[self.df['timestep'] == timestep]
        active_sats = set(current_data['satellite_id'])

        # Remover satélites que já não estão visíveis
        for sat_id in list(self.satellites.keys()):
            if sat_id not in active_sats:
                node_id = self.satellites.pop(sat_id)
                self.sim.static_nodes.remove(node_id)
                constellation_row = self.df[self.df['satellite_id'] == sat_id].iloc[0]
                constellation = constellation_row['constellation_name']
                for (app_name, module_name) in self.modules_alloc_sat.get(constellation, []):
                    self.sim.undeploy_module(app_name, module_name, node_id)
                if node_id in self.sim.topology.G.nodes:
                    print("Satélite removido:", node_id)
                    self.sim.remove_node(node_id)
                    #self.sim.topology.G.remove_edges_from(list(self.sim.topology.G.edges(node_id)))
                    #self.sim.topology.G.remove_node(node_id)

        for _, row in current_data.iterrows():
            sat_id = str(row["satellite_id"])
            constellation = row["constellation_name"]
            x = row["latitude"]
            y = row["longitude"]

            if sat_id in self.satellites and self.satellites[sat_id] in self.sim.topology.G.nodes:
                # Atualiza a posição
                self.sim.topology.G.nodes[self.satellites[sat_id]]['pos'] = (row["sub_lat"], row["sub_lon"])
                self.sim.topology.G.nodes[sat_id]['sub_pos'] = (x,y)
                self.sim.topology.G.nodes[sat_id]['time'] = row["time"]
                self.sim.topology.G.nodes[sat_id]['altitude'] = row["altitude"]
                self.sim.topology.G.nodes[sat_id]["raan"] = row["raan"]
                self.sim.topology.G.nodes[sat_id]["mo"] = row["mo"]
                if self.sim.topology.energy_model is not None:
                    self.sim.topology.energy_model.update_cpu_energy_consumption(self.sim.topology, sat_id, self.sim.env.now, self.__parse_interval_unit(self.next_timestep, 's'))

            else:
                # Adiciona novo satélite visível
                self.sim.topology.G.add_node(sat_id, type="SATELLITE", IPT=self.node_atr[constellation][0], RAM=self.node_atr[constellation][1])
                self.sim.topology.G.nodes[sat_id]['pos'] = (row["sub_lat"], row["sub_lon"])
                self.sim.topology.G.nodes[sat_id]['sub_pos'] = (x,y)
                self.sim.topology.G.nodes[sat_id]["coverage_radius_km"] = row["coverage_radius_km"]
                self.sim.topology.G.nodes[sat_id]["coverage_angle_rad"] = row["coverage_angle_rad"]
                self.sim.topology.G.nodes[sat_id]['time'] = row["time"]
                self.sim.topology.G.nodes[sat_id]['altitude'] = row["altitude"]
                self.sim.topology.G.nodes[sat_id]["raan"] = row["raan"]
                self.sim.topology.G.nodes[sat_id]["mo"] = row["mo"]
                self.sim.topology.G.nodes[sat_id]["constellation_name"] = row["constellation_name"]
                self.sim.static_nodes.append(sat_id)
                if self.sim.topology.energy_model is not None:
                    self.sim.topology.energy_model.update_cpu_energy_consumption(self.sim.topology, sat_id, self.sim.env.now, self.__parse_interval_unit(self.next_timestep, 's'))

                for app_name, module_name in self.modules_alloc_sat.get(constellation, []):
                    app = self.s.apps[app_name]
                    services = app.services
                    self.s.deploy_module(app_name, module_name, services[module_name], [sat_id])

                self.satellites[sat_id] = sat_id

    def run(self, time):
        self.update_satellite_positions(time)    
        #for node, data in self.sim.topology.G.nodes(data=True):
        #    print(f"Nó: {node}")
        #    print(f"Atributos: {data}")
        #    print("-" * 30)
        
    def __parse_interval_unit(self, value, unit):
        units = {
            'ms': timedelta(milliseconds=1),
            's': timedelta(seconds=1),
            'm': timedelta(minutes=1),
            'h': timedelta(hours=1)
        }
        return value * units[unit] 
    
    def __fetch_satellites(self, constellation, ts):
        source = constellation.get("source", "celestrak")
        name = constellation.get("name", "Unnamed")

        if source == "celestrak":
            data_format = constellation.get("format", "json")
            base = 'https://celestrak.org/NORAD/elements/gp.php'
            url = f"{base}?GROUP={name}&FORMAT={data_format}"
            if data_format == "json":   
                filename = f"{name}.json"
            else: 
                filename = f"{name}.tle"
                
            if not load.exists(filename) or load.days_old(filename) >= 7:
                load.download(url, filename=filename)
                
            with load.open(filename) as f:
                if data_format == "json":
                    data = json.load(f)
                    sats = [EarthSatellite.from_omm(ts, fields) for fields in data]
                else:
                    sats = list(parse_tle_file(f, ts))
                    
            print(f"[{name}] Loaded {len(sats)} satellites from Celestrak")
            for sat in sats:
                sat.constellation_name = name
            return sats

        elif source == "manual":
            tle_list = constellation.get("tle", [])
            sats = []
            for sat in tle_list:
                line1 = sat["line1"]
                line2 = sat["line2"]
                sat_name = sat.get("name", "CustomSat")
                sats.append(EarthSatellite(line1, line2, sat_name, ts))
            
            for sat in sats:
                sat.constellation_name = name
                
            if name.lower() == "mist_synthetic":
                sats = [sat for i, sat in enumerate(sats) if i % 10 != 0]  # Remove 1 a cada 10 (i % 10 == 0)
            print(f"[{name}] Loaded {len(sats)} custom satellites")
            return sats

        else:
            print(f"Unknown source '{source}' in constellation {name}")
            return []