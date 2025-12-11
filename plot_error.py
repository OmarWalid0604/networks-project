import csv
import numpy as np
import matplotlib.pyplot as plt

ERROR_FILE = "error_results.csv"

def load_errors():
    snap_ids = []
    errors = []
    with open(ERROR_FILE, "r") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for snap, pid, sx, sy, dx, dy, err in reader:
            snap_ids.append(int(snap))
            errors.append(float(err))
    return snap_ids, errors

def main():
    snap_ids, errors = load_errors()

    errors_np = np.array(errors)
    mean_error = float(np.mean(errors_np))
    p95_error = float(np.percentile(errors_np, 95))

    print("===== ERROR STATISTICS =====")
    print(f"Mean error: {mean_error:.3f}")
    print(f"95th percentile error: {p95_error:.3f}")

    # -----------------------------
    # Plot error over snapshot_id
    # -----------------------------
    plt.figure(figsize=(10, 5))
    plt.plot(snap_ids, errors, linewidth=1)
    plt.xlabel("Snapshot ID")
    plt.ylabel("Perceived Error (units)")
    plt.title("Error Over Time")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("error_time.png")
    plt.close()

    # -----------------------------
    # Histogram
    # -----------------------------
    plt.figure(figsize=(8, 5))
    plt.hist(errors, bins=40, alpha=0.7)
    plt.xlabel("Error")
    plt.ylabel("Count")
    plt.title("Error Distribution")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("error_hist.png")
    plt.close()

    print("Plots generated: error_time.png, error_hist.png")

if __name__ == "__main__":
    main()
