import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

CONFIG_LABELS = {
    "only_fog_in_terrestrial_nodes": "terrestrial fog computation",
    "fog_in_terrestrial_and_satellites_nodes": "fog computation in both",
    "hybrid": "no fog computation"
}

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
    
    present_ids = set()
    
    for task_id, group in groups:
        sorted_group = group.sort_values(by="time_out")

        messages = list(sorted_group['message'])
        app_name = sorted_group.iloc[0]['app']  # assumindo que o app não muda no mesmo grupo

        # Verifica se as mensagens estão presentes
        if start_message in messages and end_message in messages:
            if app_name in app_deadlines:
                present_ids.add(task_id)
                deadline = app_deadlines[app_name]

                # Busca a primeira ocorrência do start_message
                start_row = sorted_group[sorted_group['message'] == start_message].iloc[0]
                # Busca a última ocorrência do end_message
                end_row = sorted_group[sorted_group['message'] == end_message].iloc[-1]

                time_emit = start_row['time_emit']
                time_out_last = end_row['time_out']
                e2e_delay = time_out_last - time_emit

                if e2e_delay <= deadline:
                    
                    valid_tasks += 1
                else:
                    invalid_by_latency += 1
                valid_delays.append(e2e_delay)
            else:
                print(f"Warning: No deadline defined for app '{app_name}' (task {task_id}), skipping...")
        #else:
        #    if sorted_group['time_reception'].iloc[-1] < 3400:
        #        invalid_by_mobility += 1
            # Pega o time_reception da última mensagem desse grupo
            
    # --- NOVO cálculo de invalid_by_mobility ---
    all_ids_in_file = sorted(df['id'].unique())
    full_expected_ids = set(range(min(all_ids_in_file), max(all_ids_in_file) + 1))

    # Falta de IDs (não aparecem no CSV como um todo)
    missing_ids = full_expected_ids - set(all_ids_in_file)

    # Falta de tarefas completas (ID aparece, mas incompleto)
    #incomplete_ids = set(all_ids_in_file) - present_ids

    # Total de inválidos por mobilidade: IDs faltando ou incompletos
    invalid_by_mobility = len(missing_ids) 

    average_delay = sum(valid_delays) / (len(valid_delays))  if valid_delays else 0

    return (
        average_delay,
        valid_tasks,
        invalid_by_latency,
        invalid_by_mobility,
    )

def count_processing_locations(csv_path):
    df = pd.read_csv(csv_path)

    cloud_count = df[(df['message'] == 'raw_data_to_cloud') & (df['TOPO.dst'].str.startswith('cloud'))].shape[0]
    node_count = df[(df['message'] == 'raw_data_to_cloud') & (df['TOPO.dst'].str.startswith('node'))].shape[0]
    sat_count = df[(df['message'] == 'raw_data_to_cloud') & (df['TOPO.dst'].str.startswith('ONEWEB'))].shape[0]

    return cloud_count, node_count, sat_count



def count_completed_tasks_per_interval(csv_path, start_message, end_message, interval=600):
    df = pd.read_csv(csv_path)
    groups = df.groupby("id")

    task_times = []

    for task_id, group in groups:
        sorted_group = group.sort_values(by="time_out")
        messages = list(sorted_group['message'])
        
        if start_message in messages and end_message in messages:
            try:
                end_row = sorted_group[sorted_group['message'] == end_message].iloc[-1]
                completed_time = end_row['time_out']
                task_times.append(completed_time)
            except:
                continue

    # Agrupar por intervalos de 30 segundos
    if not task_times:
        return pd.Series(dtype=int)

    max_time = max(task_times)
    bins = np.arange(0, max_time + interval, interval)
    counts, _ = np.histogram(task_times, bins=bins)
    intervals = [f"{int(bins[i])}-{int(bins[i+1])}" for i in range(len(counts))]

    return pd.Series(counts, index=intervals)



app_deadlines = {
    "EMERGENCY_APP": 30,
}


CONFIGURATIONS = ["only_fog_in_terrestrial_nodes", "fog_in_terrestrial_and_satellites_nodes", "hybrid"]
N_TESTS = 3

BASE_PATH = "D:/YAFS_results/Test_SatellitesInFog/results"


def aggregate_results():
    summary = []
    task_series_by_config = {}

    for config in CONFIGURATIONS:
        delays = []
        valid_tasks_list = []
        invalid_latency_list = []
        invalid_mobility_list = []
        
        time_series = pd.Series(dtype=int)
        cloud_total = 0
        node_total = 0
        sat_total = 0

        for i in range(1, N_TESTS + 1):
            test_dir = os.path.join(BASE_PATH, config, f"test_{i}")
            delay_csv = os.path.join(test_dir, "sim_trace.csv")

            try:
                (
                    avg_delay, valid_tasks, invalid_latency, invalid_mobility,
                ) = analyse_e2e_delay(
                    delay_csv,
                    start_message="sensor_data",
                    end_message="Emergency_notification",
                    app_deadlines=app_deadlines
                )

                # Acumular valores
                delays.append(avg_delay)
                valid_tasks_list.append(valid_tasks)
                invalid_latency_list.append(invalid_latency)
                invalid_mobility_list.append(invalid_mobility)
                
                interval_counts = count_completed_tasks_per_interval(
                    delay_csv,
                    start_message="sensor_data",
                    end_message="Emergency_notification",
                    interval=600
                )
                time_series = time_series.add(interval_counts, fill_value=0)
                cloud, node, sat = count_processing_locations(delay_csv)
                cloud_total += cloud
                node_total += node
                sat_total += sat


            except Exception as e:
                print(f"[ERROR] Failed to process {test_dir}: {e}")
                continue

        if delays:
            summary.append({
                "configuration": config,
                "avg_e2e_delay": np.mean(delays),
                "avg_valid_tasks": np.mean(valid_tasks_list),
                "avg_invalid_latency": np.mean(invalid_latency_list),
                "avg_invalid_mobility": np.mean(invalid_mobility_list),
                "tasks_cloud": cloud_total/ N_TESTS,
                "tasks_terrestrial": node_total/ N_TESTS,
                "tasks_satellite": sat_total/ N_TESTS,
            })
            task_series_by_config[config] = time_series

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv("aggregated_results.csv", index=False)
    print(summary_df)
    
    plt.figure(figsize=(10, 6))
    for config, series in task_series_by_config.items():
        series.sort_index(inplace=True)
        pretty_label = CONFIG_LABELS.get(config, config)  # usa o label mais descritivo
        plt.plot(series.index, series.values, label=pretty_label)

    plt.xlabel("Time Interval (s)")
    plt.ylabel("Completed Tasks")
    plt.title("Completed Tasks Every 10 Minutes")
    plt.xticks(rotation=45)
    plt.grid(False)
    plt.legend()
    plt.tight_layout()
    plt.show()



aggregate_results()



df = pd.read_csv("aggregated_results.csv")

def plot_processing_distribution():
    df_avg = df[["configuration", "tasks_cloud", "tasks_terrestrial", "tasks_satellite"]].copy()
    df_avg.index = df_avg["configuration"].map(CONFIG_LABELS)
    df_avg.drop("configuration", axis=1, inplace=True)

    ax = df_avg.plot(kind='bar', figsize=(10, 6))

    plt.ylabel("Average Number of Tasks")
    plt.title("Average Tasks Processed by Location")
    plt.xticks(rotation=0)
    plt.grid(False)

    # Adiciona valores acima das barras
    for p in ax.patches:
        height = p.get_height()
        if height > 0:
            ax.annotate(f'{int(height)}', (p.get_x() + p.get_width() / 2, height),
                        ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.show()

    

plot_processing_distribution()

metrics = {
    "avg_e2e_delay": "Average E2E Delay (s)",
    "success_rate": "Success Rate (%)",
    "failed_latency_rate": "Failed by Latency (%)",
    "failed_mobility_rate": "Failed by Mobility (%)"
}

# Calcular taxas
df['total_tasks'] = df['avg_valid_tasks'] + df['avg_invalid_latency'] + df['avg_invalid_mobility']
df['success_rate'] = (df['avg_valid_tasks'] / df['total_tasks']) * 100
df['failed_latency_rate'] = (df['avg_invalid_latency'] / df['total_tasks']) * 100
df['failed_mobility_rate'] = (df['avg_invalid_mobility'] / df['total_tasks']) * 100

def plot_bar(metric, ylabel):
    x_labels = df['configuration'].map(CONFIG_LABELS)
    plt.figure(figsize=(7, 5))
    bars = plt.bar(x_labels, df[metric], color=['blue', 'green', 'orange'])
    plt.xlabel("Network Configuration")
    plt.ylabel(ylabel)
    plt.title(ylabel)
    plt.grid(False)
    
    
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.04, f'{height:.3f}', ha='center', fontsize=9)
   
    plt.tight_layout()
    plt.show()

for metric, label in metrics.items():
    plot_bar(metric, label)
