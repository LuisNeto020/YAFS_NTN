import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Point
import contextily as ctx
import numpy as np
import cv2

from pyproj import Proj, Transformer

class VehicleMap:
    def __init__(self, csv_file):
        self.df = pd.read_csv(csv_file, delimiter=';')  # Ajustar delimitador se necessário
        
        # Definir os limites do mapa baseado no SUMO
        self.map_bounds = {
            "min_lon": -8.309739, "min_lat": 41.662532,
            "max_lon": -7.884646, "max_lat": 41.809652
        }

        
    def plot_vehicles(self, output_video="vehicles.mp4", fps=15):
        
        timesteps = sorted(self.df["timestep_time"].unique())
        timesteps = timesteps[::10]

        figsize = (16, 9)
        # Criar o mapa com os limites exatos do SUMO
        fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
        ax.set_xlim(self.map_bounds["min_lon"], self.map_bounds["max_lon"])
        ax.set_ylim(self.map_bounds["min_lat"], self.map_bounds["max_lat"])

        # Adicionar OpenStreetMap como base
        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, crs="EPSG:4326")

        # Definir limites do mapa conforme os valores do SUMO
        scatter, = ax.plot([], [], 'ro', markersize=5)

        # Definir a resolução correta para o vídeo
        width = int(figsize[0] * 100)  # largura = figsize[0] * dpi
        height = int(figsize[1] * 100)  # altura = figsize[1] * dpi
        print(height, width)

        # Criar o gravador de vídeo com resolução correta
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec para MP4
        video_writer = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

        for timestep in timesteps:
            current_data = self.df[self.df["timestep_time"] == timestep]
            
            if current_data["vehicle_x"].dropna().empty:
                x = current_data["person_x"]
                y = current_data["person_y"]
            else:
                x = current_data["vehicle_x"]
                y = current_data["vehicle_y"]

            # Atualizar pontos sem recriar o scatter
            scatter.set_data(x, y)
            ax.set_title(f"Posição dos Veículos - Timestep {timestep}")

            # Salvar o frame no OpenCV
            fig.canvas.draw()
            frame = np.array(fig.canvas.renderer.buffer_rgba())
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            video_writer.write(frame)

        # Fechar o vídeo e liberar memória
        video_writer.release()
        plt.close(fig)
     
csv_path = r"C:\Users\WRT511\OneDrive\Curso\YAFS_NTN\examples\SatellitesAsaBridge\fcd_output_filtered.csv"        
mapa = VehicleMap(csv_path)
mapa.plot_vehicles()
