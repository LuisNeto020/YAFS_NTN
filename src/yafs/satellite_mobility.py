from datetime import datetime, timedelta
import pandas as pd
import os
import json
from skyfield.api import load, EarthSatellite, Topos, wgs84
from skyfield.iokit import parse_tle_file
from math import cos, radians, asin
import logging

class SatelliteMobility:
    
    """
    Manages the mobility and visibility of satellites in the simulation.

    Attributes:
        json_data (dict): JSON configuration with satellite and constellation info.
        next_timestep (int): Time interval for the next position update.
        df (pd.DataFrame): Cached or computed satellite positions.
        satellites (dict): Mapping of active satellite IDs to simulation nodes.
        modules_alloc_sat (dict): Modules allocated to each constellation.
        node_atr (dict): Node attributes (IPT, RAM) for each constellation.
        consumption_atr (dict): Power consumption attributes for satellites {constellation name : {"maxIdleConsumption": max_idle, "maxActiveConsumption": max_active}, ... }.
        sim (Simulation): Reference to the simulation environment.
        data_cache_path (str): Path to store/load cached satellite data.
    """
    EARTH_RADIUS_KM = 6371.0
    
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
        """
        Returns the next timestep for updating satellite positions.

        Returns:
            int: Next activation timestep.
        """
        return self.next_timestep
    
    
    def use_all_sat(self):
        """
        Loads or computes all satellite positions for the simulation.

        If a cached CSV exists at `data_cache_path`, it is loaded. Otherwise,
        satellite positions are computed for all constellations and timesteps,
        including altitude, coverage radius, and other orbital parameters.

        Populates:
            - `df`: DataFrame with satellite positions and attributes.
            - `node_atr`: Node attributes for each constellation.
            - `consumption_atr`: Energy consumption attributes for satellites.
            - Adds satellite nodes to `sim.topology.G` with their properties.

        Returns:
            pd.DataFrame: DataFrame with satellite positions and attributes.
        """
        if os.path.exists(self.data_cache_path):
            logging.info("Cache found at '%s'. Loading...", self.data_cache_path)
            ts = load.timescale()
            self.df["time"] = self.df["time"].apply(lambda t: ts.utc(pd.to_datetime(t).to_pydatetime()))

        else:
            self.df = self._compute_satellite_positions()

        self._initialize_node_attributes()
        self._add_satellites_to_graph(timestep=0)
        return self.df
            
    def initial_sat_info(self):
        
        """
        Computes satellite positions and visibility relative to a central observer, and only these satellites are calculated during the simulation.

        Checks for cached data; if not found, computes visibility windows and 
        satellite positions over the simulation period.

        Populates:
            - `df`: DataFrame with initial satellite positions.
            - `modules_alloc_sat`: Allocated modules per constellation.
            - `node_atr`: Node attributes for each constellation.

        Returns:
            pd.DataFrame: DataFrame with satellite positions and visibility info.
        """
        
        if os.path.exists(self.data_cache_path):
            logging.info("Cache found at '%s'. Loading...", self.data_cache_path)
            self.df = pd.read_csv(self.data_cache_path)
            ts = load.timescale()
            self.df["time"] = self.df["time"].apply(lambda t: ts.utc(pd.to_datetime(t).to_pydatetime()))

        else:
            self.df = self._compute_visible_satellite_positions()

        self._initialize_node_attributes()
        logging.info("Initial satellite info computed. Sample:\n%s", self.df.head())
        return self.df
    
    def _compute_satellite_positions(self):
        """
        Compute positions of all satellites in all constellations over the simulation period.


        Returns:
        pd.DataFrame: DataFrame containing positions, coverage, and orbital parameters.
        """
        ts = load.timescale()
        
        start_time = datetime.fromisoformat(self.json_data["time_interval"]["start_time"].replace("Z", "+00:00"))
        duration = self.json_data["time_interval"]["duration"]
        duration_unit = self.json_data["time_interval"]["unit"]
        interval_value = self.json_data["time_interval"]["check_frequency"]
        end_time = start_time + self.__parse_interval_unit(duration, duration_unit.lower())
        interval = self.__parse_interval_unit(interval_value, duration_unit.lower())
        
        min_altitude = self.json_data.get("minimum_altitude_angle", 0.0)
        # Load satellites from all constellations
        satellites = []
        for constellation in self.json_data["constellations"]:
            satellites += self.__fetch_satellites(constellation, ts)
            
        records = []

        timestep = 0
        current_time = start_time
        while current_time <= end_time:
            t = ts.utc(current_time.year, current_time.month, current_time.day,
                       current_time.hour, current_time.minute, current_time.second)
            for sat in satellites:
                records.append(self._compute_satellite_record(sat, t, timestep, min_altitude))
            timestep += self.next_timestep
            current_time += interval

        df = pd.DataFrame(records)
        dtt= pd.DataFrame(records)
        dtt["time"] = dtt["time"].apply(lambda t: t.utc_iso())
        dtt.to_csv(self.data_cache_path, index=False)
        return df
    
    def _compute_satellite_record(self, sat, t, timestep, min_altitude: float):
        """
        Compute a single satellite record at a given timestep.


        Args:
        sat (EarthSatellite): Satellite object.
        t (Time): Skyfield time object.
        timestep (int): Simulation timestep.
        min_altitude (float): Minimum altitude angle in degrees.


        Returns:
        dict: Satellite state with position, altitude, coverage, and orbital params.
        """
        geocentric = sat.at(t)
        sat_lat, sat_lon = wgs84.latlon_of(geocentric)
        subpoint = geocentric.subpoint()
        sat_alt_km = wgs84.height_of(geocentric).km
        # Compute coverage radius based on altitude and min elevation
        epsilon_0_rad = radians(min_altitude)
        sin_alpha_0 = (self.EARTH_RADIUS_KM / (self.EARTH_RADIUS_KM + sat_alt_km)) * cos(epsilon_0_rad)
        alpha_0_rad = asin(sin_alpha_0)
        beta_0_rad = radians(90) - epsilon_0_rad - alpha_0_rad
        coverage_radius_km = self.EARTH_RADIUS_KM * beta_0_rad

        return {
            "timestep": timestep,
            "time": t,
            "satellite_id": sat.name,
            "constellation_name": getattr(sat, "constellation_name", "Unknown"),
            "latitude": sat_lat.degrees,
            "longitude": sat_lon.degrees,
            "sub_lat": subpoint.latitude.degrees,
            "sub_lon": subpoint.longitude.degrees,
            "altitude": sat_alt_km,
            "coverage_radius_km": coverage_radius_km,
            "coverage_angle_rad": beta_0_rad,
            "raan": sat.model.nodeo,
            "mo": sat.model.mo
        }
        
    def _compute_visible_satellite_positions(self):
        """
        Compute positions only for satellites visible from the defined observer.


        Returns:
        pd.DataFrame: DataFrame with visible satellite positions only.
        """
        ts = load.timescale()
        
        start_time = datetime.fromisoformat(self.json_data["time_interval"]["start_time"].replace("Z", "+00:00"))
        duration = self.json_data["time_interval"]["duration"]
        duration_unit = self.json_data["time_interval"]["unit"]
        interval_value = self.json_data["time_interval"]["check_frequency"]
        end_time = start_time + self.__parse_interval_unit(duration, duration_unit.lower())
        interval = self.__parse_interval_unit(interval_value, duration_unit.lower())
        
        min_altitude = self.json_data.get("minimum_altitude_angle", 0.0)

        observer_lat = (self.json_data["latitude"]["min"] + self.json_data["latitude"]["max"]) / 2
        observer_lon = (self.json_data["longitude"]["min"] + self.json_data["longitude"]["max"]) / 2
        observer = Topos(latitude_degrees=observer_lat, longitude_degrees=observer_lon)

        
        satellites = []
        for constellation in self.json_data["constellations"]:
            satellites += self.__fetch_satellites(constellation, ts)
        
        visibility_windows = {sat.name: self.__get_visibility_intervals(sat, observer, ts, start_time, end_time, min_altitude)
                              for sat in satellites}

        records = []
        timestep = 0
        current_time = start_time
        while current_time <= end_time:
            t = ts.utc(current_time.year, current_time.month, current_time.day,
                       current_time.hour, current_time.minute, current_time.second)
            for sat in satellites:
                if not self.__is_visible(current_time, visibility_windows.get(sat.name, [])):
                    continue
                records.append(self._compute_satellite_record(sat, t, timestep, min_altitude))
            timestep += self.next_timestep
            current_time += interval

        df = pd.DataFrame(records)
        dtt= pd.DataFrame(records)
        dtt["time"] = dtt["time"].apply(lambda t: t.utc_iso())
        dtt.to_csv(self.data_cache_path, index=False)
        return df
        
    def _initialize_node_attributes(self):
        """
        Initialize node attributes (IPT, RAM, energy consumption) for each constellation.
        """
        for constellation in self.json_data["constellations"]:
            name = constellation["name"]
            self.node_atr[name] = (constellation.get("IPT", 0), constellation.get("RAM", 0))
            max_idle = constellation.get("maxIdleConsumption")
            max_active = constellation.get("maxActiveConsumption")
            if max_idle is not None and max_active is not None:
                self.consumption_atr[name] = {"maxIdleConsumption": max_idle, "maxActiveConsumption": max_active}
                
    def _add_satellites_to_graph(self, timestep=0):
        """
        Add satellites at a given timestep into the simulation topology graph.


        Args:
        timestep (int): Timestep to extract positions from the DataFrame.
        """
        current_data = self.df[self.df['timestep'] == timestep]
        for _, row in current_data.iterrows():
            sat_id = str(row["satellite_id"])
            constellation = row["constellation_name"]
            x, y = row["latitude"], row["longitude"]

            self.sim.topology.G.add_node(
                sat_id,
                type="SATELLITE",
                IPT=self.node_atr[constellation][0],
                RAM=self.node_atr[constellation][1],
                pos=(row["sub_lat"], row["sub_lon"]),
                sub_pos=(x, y),
                coverage_radius_km=row["coverage_radius_km"],
                coverage_angle_rad=row["coverage_angle_rad"],
                time=row["time"],
                altitude=row["altitude"],
                raan=row["raan"],
                mo=row["mo"],
                constellation_name=constellation,
                maxIdleConsumption=self.consumption_atr.get(constellation, {}).get("maxIdleConsumption"),
                maxActiveConsumption=self.consumption_atr.get(constellation, {}).get("maxActiveConsumption")
            )
            self.sim.static_nodes.append(sat_id)
    
    def __get_visibility_intervals(self, satellite, observer, ts, start_time, end_time, min_altitude=0.0):
        """
        Computes visibility intervals for a given satellite and observer.

        Args:
            satellite (EarthSatellite): Satellite object.
            observer (Topos): Observer location.
            ts (Timescale): Skyfield timescale.
            start_time (datetime): Start of the visibility period.
            end_time (datetime): End of the visibility period.
            min_altitude (float): Minimum elevation angle in degrees.

        Returns:
            list[dict]: List of visibility windows with 'start' and 'end' keys.
        """
        
        t0 = ts.utc(start_time.year, start_time.month, start_time.day,
                    start_time.hour, start_time.minute, start_time.second)
        t1 = ts.utc(end_time.year, end_time.month, end_time.day,
                    end_time.hour, end_time.minute, end_time.second)

        t_events, events = satellite.find_events(observer, t0, t1, altitude_degrees=min_altitude)
        visibility_windows = []
        current_window = None

        # if the first event is a rise (0) or culmination (1), it was already visible
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
        # if still in a window on the end time
        if current_window:
            current_window["end"] = end_time
            visibility_windows.append(current_window)
            
        if len(events) == 0:
            alt, _, _ = (satellite-observer).at(t0).altaz()
            if alt.degrees >= min_altitude:
                visibility_windows.append({"start": start_time, "end": end_time})
        return visibility_windows


    def __is_visible(self, current_time, windows):
        """
        Checks if the current time is within any visibility window.

        Args:
            current_time (datetime): Time to check visibility.
            windows (list[dict]): List of visibility intervals.

        Returns:
            bool: True if visible, False otherwise.
        """
        for window in windows:
            if window["start"] <= current_time <= window["end"]:
                return True
        return False
    
    def _undeploy_allocated_modules(self, constellation, node_id):
        """
        Undeploy all modules previously allocated to a given node.


        This is used before removing a satellite node from the topology to ensure
        clean teardown of application modules.


        Args:
        constellation (str): Constellation name that owns the modules.
        node_id (str): Identifier of the node (satellite) in the simulation graph.
        """
        for app_name, module_name in self.modules_alloc_sat.get(constellation, []):
            try:
                self.sim.undeploy_module(app_name, module_name, node_id)
            except Exception as e:
                logging.debug("failure in undeploying %s/%s from node %s: %s", app_name, module_name, node_id, e)

    def _get_constellation_of_sat(self, sat_id):
        """
        Infer the constellation name for a satellite.


        Attempts to read from the current graph node data; if unavailable,
        looks up the information in the internal DataFrame.


        Args:
        sat_id (str): Satellite identifier (node name).


        Returns:
        str: Constellation name, or "Unknown" if not found.
        """
        G = self.sim.topology.G
        if sat_id in G.nodes and "constellation_name" in G.nodes[sat_id]:
            return G.nodes[sat_id]["constellation_name"]
        try:
            return self.df.loc[self.df["satellite_id"] == sat_id, "constellation_name"].iloc[0]
        except Exception:
            return "Unknown"

      
    def _remove_inactive_satellites(self, active_sat_ids):
        """
        Remove satellite nodes that are no longer active/visible at the current timestep.


        The routine:
        1) Identifies satellites missing from the active set,
        2) Undeploys any allocated modules,
        3) Removes them from the static list,
        4) Removes the node from the graph.


        Args:
        active_sat_ids: Set of satellite IDs that should remain active.
        """
        to_remove = [sid for sid in self.satellites.keys() if sid not in active_sat_ids]
        if not to_remove:
            return

        for sat_id in to_remove:
            node_id = self.satellites.pop(sat_id, None)
            if node_id is None:
                continue

            # Undeploy modules associated with this satellite
            constellation = self._get_constellation_of_sat(sat_id)
            self._undeploy_allocated_modules(constellation, node_id)


            # Remove from the static nodes list
            try:
                self.sim.static_nodes.remove(node_id)
            except ValueError:
                pass

            # Remove from the graph
            if node_id in self.sim.topology.G.nodes:
                try:
                    self.sim.remove_node(node_id)
                    logging.info("Satellite removed: %s", node_id)
                except Exception as e:
                    logging.warning("Failed to remove node %s: %s", node_id, e)
  
        
    def update_satellite_positions(self, timestep):
        """
        Updates or adds satellites in the simulation topology for the given timestep.

        - Removes satellites that are no longer visible.
        - Updates positions of currently visible satellites.
        - Adds new visible satellites to the topology and deploys allocated modules.
        - Updates energy consumption if the simulation energy model is active.

        Args:
            timestep (int): Current simulation timestep to update satellite positions.
        """
        
        if self.df is None:
            logging.error("Satellite DataFrame is not initialized. Call 'use_all_sat' or 'initial_sat_info' first")
            return
        
        current_data = self.df[self.df['timestep'] == timestep]
        active_sats = set(current_data["satellite_id"].astype(str))

        # Remove satellites that are no longer visible at this timestep
        self._remove_inactive_satellites(active_sats)
                   

        for _, row in current_data.iterrows():
            sat_id = str(row["satellite_id"])
            constellation = row["constellation_name"]
            x = row["latitude"]
            y = row["longitude"]

            if sat_id in self.satellites and self.satellites[sat_id] in self.sim.topology.G.nodes:
                # Update position and dynamic attributes
                self.sim.topology.G.nodes[self.satellites[sat_id]]['pos'] = (row["sub_lat"], row["sub_lon"])
                self.sim.topology.G.nodes[sat_id]['sub_pos'] = (x,y)
                self.sim.topology.G.nodes[sat_id]['time'] = row["time"]
                self.sim.topology.G.nodes[sat_id]['altitude'] = row["altitude"]
                self.sim.topology.G.nodes[sat_id]["raan"] = row["raan"]
                self.sim.topology.G.nodes[sat_id]["mo"] = row["mo"]
                if self.sim.topology.energy_model is not None:
                    self.sim.topology.energy_model.update_cpu_energy_consumption(self.sim.topology, sat_id, self.sim.env.now, self.__parse_interval_unit(self.next_timestep, 's'))

            else:
                # Add newly visible satellite node
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

                self.satellites[sat_id] = sat_id

    def run(self, time):
        self.update_satellite_positions(time)    
        
        
    def __parse_interval_unit(self, value, unit):
        units = {
            'ms': timedelta(milliseconds=1),
            's': timedelta(seconds=1),
            'm': timedelta(minutes=1),
            'h': timedelta(hours=1)
        }
        return value * units[unit] 
    
    def _fetch_from_celestrak(self, constellation, ts):
        name = constellation.get("name", "Unnamed")
        data_format = (constellation.get("format") or "json").lower()
        base = "https://celestrak.org/NORAD/elements/gp.php"
        url = f"{base}?GROUP={name}&FORMAT={data_format}"
        filename = f"{name}.{ 'json' if data_format == 'json' else 'tle' }"

        # Download if missing or stale
        try:
            if (not load.exists(filename)) or load.days_old(filename) >= 7:
                logging.info("[%s] Downloading TLE/OMM elements from Celestrak...", name)
                load.download(url, filename=filename)
        except Exception as e:
            logging.warning("[%s] Could not download %s (will use cache if available): %s", name, url, e)

        # Read local cached file
        if data_format == "json":
            with load.open(filename) as fh:
                data = json.load(fh)
            sats = [EarthSatellite.from_omm(ts, fields) for fields in data]
            return sats

        # TLE format
        try:
            with load.open(filename) as fh:
                sats = list(parse_tle_file(fh, ts))
            return sats
        except Exception:
            # Portable fallback
            sats = load.tle_file(filename)  
            return sats
    
    def __fetch_satellites(self, constellation, ts):
        """
        Fetches satellites for a given constellation, either from an online source
        (Celestrak) or from manually provided TLE data.

        Parameters:
            constellation (dict): A dictionary containing constellation information.
                Expected keys:
                    - "source" (str): Source of the satellite data ("celestrak" or "manual").
                    - "name" (str): Name of the constellation.
                    - "format" (str, optional): Data format for Celestrak ("json" or "tle"). Defaults to "json".
                    - "tle" (list of dict, optional): List of manually provided TLEs with keys "line1", "line2", and optional "name".
            ts (Timescale): A skyfield Timescale object for initializing EarthSatellite objects.

        Returns:
            list[EarthSatellite]: A list of EarthSatellite objects corresponding to the constellation.
                Each satellite object will have the `constellation_name` attribute set to the constellation's name.
                Returns an empty list if the source is unknown.

        Notes:
            - If using Celestrak, the data is cached locally and refreshed if older than 7 days.
        """
        source = constellation.get("source", "celestrak").lower()
        name = constellation.get("name", "Unnamed")

        if source == "celestrak":
            sats = self._fetch_from_celestrak(constellation, ts)
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
            logging.info("[%s] Loaded %d custom satellites", name, len(sats))
            return sats

        else:
            logging.warning("Unknown source '%s' in constellation %s", source, name)
            return []