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


app_deadlines = {
    "EMERGENCY_APP": 30,
}


CONFIGURATIONS = ["terrestrial", "satellite", "hybrid"]
N_TESTS = 1

BASE_PATH = "D:/YAFS_results/Test_SatellitesAsaBridge/results"


def aggregate_results():
    summary = []

    for config in CONFIGURATIONS:
        delays = []
        valid_tasks_list = []
        invalid_latency_list = []
        invalid_mobility_list = []
        

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
            })

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv("aggregated_results.csv", index=False)
    print(summary_df)



#aggregate_results()

import matplotlib.pyplot as plt

# Carregar dados
df = pd.read_csv("aggregated_results.csv")

# Calcular métricas
df['total_tasks'] = df['avg_valid_tasks'] + df['avg_invalid_latency'] + df['avg_invalid_mobility']
df['success_rate'] = (df['avg_valid_tasks'] / df['total_tasks']) * 100
df['failed_latency_rate'] = (df['avg_invalid_latency'] / df['total_tasks']) * 100
df['failed_mobility_rate'] = (df['avg_invalid_mobility'] / df['total_tasks']) * 100

# Métricas
metrics = {
    "avg_e2e_delay": "Average E2E Delay (s)",
    "success_rate": "Success Rate (%)",
}

# Plot individual métricas
def plot_bar(metric, ylabel):
    plt.figure(figsize=(8, 5))
    bars = plt.bar(df['configuration'], df[metric], color='#1f77b4', width=0.35)
    plt.xlabel("Network Configuration")
    plt.ylabel(ylabel)
    plt.title(ylabel)
    #plt.grid(axis='y', linestyle='--', alpha=0.7)

    # Adiciona valores acima das barras
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.3, f'{height:.1f}', ha='center', fontsize=9)

    plt.tight_layout()
    plt.show()

# Plot métricas simples
for metric, label in metrics.items():
    plot_bar(metric, label)

# ----------------------
# Gráfico agrupado: Failed Tasks (%)
# ----------------------

x = np.arange(len(df))  # posições para cada configuração
bar_width = 0.25

plt.figure(figsize=(9, 5))

# Barras
latency_bars = plt.bar(x - bar_width/2, df["failed_latency_rate"], width=bar_width, label="Failed by Latency", color='#d62728')
mobility_bars = plt.bar(x + bar_width/2, df["failed_mobility_rate"], width=bar_width, label="Failed by Mobility", color='#2ca02c')

# Títulos e labels
plt.title("Failed Tasks (%)")
plt.ylabel("Percentage (%)")
plt.xticks(x, df["configuration"])
plt.xlabel("Network Configuration")
plt.legend()
#plt.grid(axis='y', linestyle='--', alpha=0.7)

# Valores acima das barras
for i in range(len(x)):
    plt.text(x[i] - bar_width/2, df["failed_latency_rate"][i] + 0.3, f'{df["failed_latency_rate"][i]:.1f}', ha='center', fontsize=9)
    plt.text(x[i] + bar_width/2, df["failed_mobility_rate"][i] + 0.3, f'{df["failed_mobility_rate"][i]:.1f}', ha='center', fontsize=9)

plt.tight_layout()
plt.show()
