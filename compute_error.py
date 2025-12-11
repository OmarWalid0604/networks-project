#!/usr/bin/env python3
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# -----------------------------------------------------
#   LOAD DATA
# -----------------------------------------------------
def load_csv(server_path, client_path):
    server = pd.read_csv(server_path)
    client = pd.read_csv(client_path)

    # Necessary columns must exist
    for col in ["snapshot_id", "player_id", "x", "y"]:
        if col not in server.columns:
            raise ValueError(f"Missing column '{col}' in server_positions.csv")

    for col in ["snapshot_id", "player_id", "displayed_x", "displayed_y"]:
        if col not in client.columns:
            raise ValueError(f"Missing column '{col}' in client_display.csv")

    return server, client


# -----------------------------------------------------
#   COMPUTE POSITION ERROR PER SNAPSHOT
# -----------------------------------------------------
def compute_errors(server, client):
    merged = pd.merge(
        server,
        client,
        on=["snapshot_id", "player_id"],
        how="inner"
    )

    # Compute Euclidean error
    merged["error"] = np.sqrt(
        (merged["x"] - merged["displayed_x"])**2 +
        (merged["y"] - merged["displayed_y"])**2
    )

    return merged


# -----------------------------------------------------
#   SAVE ERROR CSV AND PLOTS
# -----------------------------------------------------
def save_outputs(errors_df, out_csv, out_plot_dir):
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    os.makedirs(out_plot_dir, exist_ok=True)

    # Save CSV
    errors_df.to_csv(out_csv, index=False)

    # Time-series plot
    plt.figure(figsize=(10,5))
    plt.plot(errors_df["snapshot_id"], errors_df["error"])
    plt.xlabel("Snapshot ID")
    plt.ylabel("Position Error")
    plt.title("Position Error Over Time")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{out_plot_dir}/error_time.png")
    plt.close()

    # Histogram
    plt.figure(figsize=(6,5))
    plt.hist(errors_df["error"], bins=30)
    plt.xlabel("Error")
    plt.ylabel("Frequency")
    plt.title("Distribution of Position Error")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{out_plot_dir}/error_hist.png")
    plt.close()


# -----------------------------------------------------
#   MAIN ENTRY
# -----------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Compute client prediction error.")
    parser.add_argument("--server", required=True, help="Path to server_positions.csv")
    parser.add_argument("--client", required=True, help="Path to client_display.csv")
    parser.add_argument("--out_csv", required=True, help="Path for saving error_results.csv")
    parser.add_argument("--out_plot", required=True, help="Directory to save plots")
    args = parser.parse_args()

    server, client = load_csv(args.server, args.client)
    errors = compute_errors(server, client)
    save_outputs(errors, args.out_csv, args.out_plot)

    print("✓ Error computation complete.")
    print(f"Saved CSV → {args.out_csv}")
    print(f"Saved plots → {args.out_plot}")


if __name__ == "__main__":
    main()
