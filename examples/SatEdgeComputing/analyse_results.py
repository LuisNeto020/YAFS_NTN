import os
import pandas as pd
import numpy as np

def analyse_e2e_delay(csv_path, start_message, end_message, app_deadlines):
    """
    Analyzes end-to-end delays from a CSV file, considering per-app deadlines.

    Parameters:
    - csv_path (str): path to the CSV file.
    - start_message (str): name of the message that indicates the start of a task.
    - end_message (str): name of the message that indicates the end of a task.
    - app_deadlines (dict): dictionary mapping app names to their deadline (e.g., {"App1": 5.0})

    Returns:
    - average_delay (float): average E2E delay of valid tasks
    - valid_tasks (int): number of valid tasks
    - invalid_by_latency (int): number of tasks exceeding the app deadline
    - invalid_by_mobility (int): number of tasks with incorrect message sequence
    """
    
    df = pd.read_csv(csv_path)
    groups = df.groupby("id")

    valid_delays = []
    valid_tasks = 0
    invalid_by_latency = 0
    invalid_by_mobility = 0
    
    valid_cloud_tasks = 0
    valid_edge_tasks = 0
    valid_mist_tasks = 0

    for task_id, group in groups:
        sorted_group = group.sort_values(by="time_out")

        first_row = sorted_group.iloc[0]
        last_row = sorted_group.iloc[-1]

        first_msg = first_row['message']
        last_msg = last_row['message']
        app_name = first_row['app']  # Assuming 'app' stays constant within the task

        if first_msg == start_message and last_msg == end_message:
            if app_name in app_deadlines:
                deadline = app_deadlines[app_name]
                time_emit = first_row['time_emit']
                time_out_last = last_row['time_out']
                e2e_delay = time_out_last - time_emit

                if e2e_delay <= deadline:
                    valid_delays.append(e2e_delay)
                    valid_tasks += 1
                    
                    # Classify TOPO.dst of the last row
                    topo_dst = last_row['TOPO.src']
                    if isinstance(topo_dst, str) and topo_dst.startswith("SAT-"):
                        sat_number = int(topo_dst.split("-")[1])
                        if 90000 <= sat_number <= 90017:
                            valid_cloud_tasks += 1
                        elif 90018 <= sat_number <= 90041:
                            valid_edge_tasks += 1
                        elif sat_number > 90041:
                            valid_mist_tasks += 1
                else:
                    invalid_by_latency += 1
            else:
                print(f"Warning: No deadline defined for app '{app_name}' (task {task_id}), skipping...")
        
            
    all_ids_in_file = sorted(df['id'].unique())
    full_expected_ids = set(range(min(all_ids_in_file), max(all_ids_in_file) + 1))

    # Falta de IDs (não aparecem no CSV como um todo)
    missing_ids = full_expected_ids - set(all_ids_in_file)

    # Falta de tarefas completas (ID aparece, mas incompleto)
    #incomplete_ids = set(all_ids_in_file) - present_ids

    # Total de inválidos por mobilidade: IDs faltando ou incompletos
    invalid_by_mobility = len(missing_ids)

    average_delay = sum(valid_delays) / len(valid_delays) if valid_delays else 0

    return (
        average_delay,
        valid_tasks,
        invalid_by_latency,
        invalid_by_mobility,
        valid_cloud_tasks,
        valid_edge_tasks,
        valid_mist_tasks
    )


def analyse_energy_consumption(energy_csv_path):
    """
    Analyzes energy consumption data, calculating the average per constellation
    and returning the total in dBW.

    Parameters:
    - energy_csv_path (str): path to the energy consumption CSV.

    Returns:
    - total_energy_dbw (float): total average energy across all constellations in dBW
    - constellation_averages (dict): average energy per constellation in watts
    """
    df = pd.read_csv(energy_csv_path)

    # Group by constellation and compute average
    avg_by_constellation = df.groupby("constellation_name")["EnergyConsumption(W)"].mean().to_dict()

    # Sum the three averages
    total_avg_energy_watts = sum(avg_by_constellation.values())

    # Convert to dBW
    if total_avg_energy_watts > 0:
        total_energy_dbw = 10 * np.log10(total_avg_energy_watts)
    else:
        total_energy_dbw = float('-inf')  # or raise an exception

    return total_avg_energy_watts, avg_by_constellation


app_deadlines = {
    "AUGMENTED_REALITY": 5,
    "E_HEALTH": 200,
    "HEAVY_COMP_APP": 5
}


ALGORITHMS = ["round_robin", "trade_off", "tradi_polling", "weight_greedy"]  # Atualiza conforme necessário
USER_COUNTS = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
N_TESTS = 3

BASE_PATH = "D:/YAFS_results/Test_SatEdgeSim/results"

def aggregate_results():
    summary = []

    for algo in ALGORITHMS:
        for user_count in USER_COUNTS:
            delays = []
            energies = []
            valid_tasks_list = []
            invalid_latency_list = []
            invalid_mobility_list = []
            cloud_tasks = []
            edge_tasks = []
            mist_tasks = []

            for i in range(1, N_TESTS + 1):
                test_dir = os.path.join(BASE_PATH, algo, str(user_count), f"test_{i}")
                delay_csv = os.path.join(test_dir, "sim_trace.csv")
                energy_csv = os.path.join(test_dir, "result_energy.csv")

                try:
                    (
                        avg_delay, valid_tasks, invalid_latency, invalid_mobility,
                        cloud, edge, mist
                    ) = analyse_e2e_delay(
                        delay_csv,
                        start_message="user_request",
                        end_message="task_result",
                        app_deadlines=app_deadlines
                    )
                    total_dbw, _ = analyse_energy_consumption(energy_csv)

                    # Acumular valores
                    delays.append(avg_delay)
                    energies.append(total_dbw)
                    valid_tasks_list.append(valid_tasks)
                    invalid_latency_list.append(invalid_latency)
                    invalid_mobility_list.append(invalid_mobility)
                    cloud_tasks.append(cloud)
                    edge_tasks.append(edge)
                    mist_tasks.append(mist)

                except Exception as e:
                    print(f"[ERROR] Failed to process {test_dir}: {e}")
                    continue

            if delays:
                summary.append({
                    "algorithm": algo,
                    "users": user_count,
                    "avg_e2e_delay": np.mean(delays),
                    "avg_energy_dbw": np.mean(energies),
                    "avg_valid_tasks": np.mean(valid_tasks_list),
                    "avg_invalid_latency": np.mean(invalid_latency_list),
                    "avg_invalid_mobility": np.mean(invalid_mobility_list),
                    "avg_cloud_tasks": np.mean(cloud_tasks),
                    "avg_edge_tasks": np.mean(edge_tasks),
                    "avg_mist_tasks": np.mean(mist_tasks),
                })

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv("aggregated_results.csv", index=False)
    print(summary_df)



results = analyse_e2e_delay(
    "D:/YAFS_results/Test_SatEdgeSim_v2/results/trade_off/1000/test_1/sim_trace.csv",
    start_message="user_request",
    end_message="task_result",
    app_deadlines=app_deadlines
)

(
    avg_delay, valid, invalid_latency, invalid_mobility,
    cloud, edge, mist
) = results

print(f"Average E2E Delay: {avg_delay:.3f}")
print(f"Valid Tasks: {valid}")
print(f"Invalid by Latency: {invalid_latency}")
print(f"Invalid by Mobility: {invalid_mobility}")
print(f"Valid Tasks in Cloud: {cloud}")
print(f"Valid Tasks in Edge: {edge}")
print(f"Valid Tasks in Mist: {mist}")
total_tasks = valid + invalid_latency + invalid_mobility
valid_tasks_percentage = (valid / total_tasks) * 100 
valid_latency_percentage = (invalid_latency / total_tasks) * 100
valid_mobility_percentage = (invalid_mobility / total_tasks) * 100
print(f"Valid Tasks Percentage: {valid_tasks_percentage:.2f}%") 
print(f"Invalid by Latency Percentage: {valid_latency_percentage:.2f}%")
print(f"Invalid by Mobility Percentage: {valid_mobility_percentage:.2f}%")


total_dbw, per_constellation_avg = analyse_energy_consumption("D:/YAFS_results/Test_SatEdgeSim_v2/results/trade_off/1000/test_1/result_energy.csv")

print(f"Total average energy (dBW): {total_dbw:.2f}")
for constellation, avg in per_constellation_avg.items():
    print(f" - {constellation}: {avg:.10f} W")
# Executar


aggregate_results()

import matplotlib.pyplot as plt

# Lê os dados do CSV
# Substitua 'dados.csv' pelo caminho correto do seu arquivo
df = pd.read_csv('aggregated_results.csv')

# Lista de algoritmos únicos
algorithms = df['algorithm'].unique()

# Dicionário para mapear cores por algoritmo (opcional)
colors = {
    'round_robin': 'blue',
    'trade_off': 'green',
    'tradi_polling': 'red',
    'weight_greedy': 'skyblue',
}

df['total_tasks'] = df['avg_valid_tasks'] + df['avg_invalid_latency'] + df['avg_invalid_mobility']
df['success_rate'] = (df['avg_valid_tasks'] / df['total_tasks']) * 100
df['failed_mobility_rate'] = (df['avg_invalid_mobility'] / df['total_tasks']) * 100
df['failed_latency_rate'] = (df['avg_invalid_latency'] / df['total_tasks']) * 100

# Função para criar gráfico
def plot_metric(metric, ylabel, title):
    plt.figure(figsize=(8, 6))
    for algo in algorithms:
        data = df[df['algorithm'] == algo]
        plt.plot(data['users'], data[metric], marker='o', label=algo, color=colors.get(algo))
    plt.xlabel('Edge devices count')
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

# 1. E2E Delay
plot_metric('avg_e2e_delay', 'Time (s)', 'Average E2E Delay (s)')

# 2. Energy Consumption
plot_metric('avg_energy_dbw', 'Consumed energy (W)', 'Average Energy Consumption')

# 3. Task Success Rate
plot_metric('success_rate', 'Success Rate (%)', 'Task Success Rate (%)')

# 4. Failed Tasks by Mobility
plot_metric('failed_mobility_rate', 'failed rate (%)', 'Task Failed Rate (mobility)(%)')

# 5. Failed Tasks by Latency
plot_metric('failed_latency_rate', 'failed rate (%)', 'Task Failed Rate (delay)(%)')
