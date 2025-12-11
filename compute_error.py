import csv
import math

SERVER_FILE = "server_positions.csv"
CLIENT_FILE = "client_display.csv"
OUTPUT_FILE = "error_results.csv"

def load_server_positions():
    server_data = {}  # (snapshot_id, player_id) -> (x, y)
    with open(SERVER_FILE, "r") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for ts, snap, pid, x, y in reader:
            key = (int(snap), int(pid))
            server_data[key] = (float(x), float(y))
    return server_data

def load_client_positions():
    client_data = {}  # (snapshot_id, player_id) -> (x, y)
    with open(CLIENT_FILE, "r") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for ts, snap, pid, dx, dy in reader:
            key = (int(snap), int(pid))
            client_data[key] = (float(dx), float(dy))
    return client_data

def compute_errors(server_data, client_data):
    results = []

    for key, (sx, sy) in server_data.items():
        if key in client_data:
            dx, dy = client_data[key]
            error = math.sqrt((sx - dx)**2 + (sy - dy)**2)
            snap, pid = key
            results.append((snap, pid, sx, sy, dx, dy, error))

    return results

def save_results(results):
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "snapshot_id",
            "player_id",
            "server_x",
            "server_y",
            "client_x",
            "client_y",
            "error"
        ])
        for row in results:
            writer.writerow(row)

def main():
    print("Loading server positions...")
    server_data = load_server_positions()

    print("Loading client displayed positions...")
    client_data = load_client_positions()

    print("Computing errors...")
    results = compute_errors(server_data, client_data)

    print(f"Saving results to {OUTPUT_FILE} ...")
    save_results(results)

    print(f"Done! {len(results)} rows processed.")

if __name__ == "__main__":
    main()
