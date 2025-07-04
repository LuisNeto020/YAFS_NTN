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
        else:
            invalid_by_mobility += 1

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

    return total_energy_dbw, avg_by_constellation


app_deadlines = {
    "AUGMENTED_REALITY": 5,
    "E_HEALTH": 200,
    "HEAVY_COMP_APP": 5
}

results = analyse_e2e_delay(
    "results/sim_trace.csv",
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


total_dbw, per_constellation_avg = analyse_energy_consumption("results/result_energy.csv")

print(f"Total average energy (dBW): {total_dbw:.2f}")
for constellation, avg in per_constellation_avg.items():
    print(f" - {constellation}: {avg:.4f} W")
