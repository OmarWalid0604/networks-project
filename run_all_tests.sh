#!/usr/bin/env bash
set -euo pipefail
# Optional verbose: uncomment to trace
# set -x

#####################################
# Phase-2 Full Test Runner
# Usage:
#  chmod +x run_all_tests.sh
#  ./run_all_tests.sh
#
# Requirements:
#  - Run on Linux (ubuntu-latest for GitHub Actions)
#  - sudo available for tc and tcpdump
#  - python3 on PATH
#  - compute_error.py and plot_error.py present in repo root
#####################################

# CONFIG
IFACE="${IFACE:-lo}"            # interface for netem (change to eth0 on VMs)
DURATION="${DURATION:-15}"      # seconds per scenario (adjust as needed)
RESULTS_DIR="${RESULTS_DIR:-results_phase2}"
SERVER_PORT="${SERVER_PORT:-7777}"
NUM_CLIENTS="${NUM_CLIENTS:-2}" # number of concurrent clients to test (2-4 recommended)
PYTHON="${PYTHON:-python3}"

# helper: apply netem (clears existing qdisc first)
apply_netem() {
  local netem_args="${1:-}"
  sudo tc qdisc del dev "$IFACE" root 2>/dev/null || true
  if [[ -n "$netem_args" ]]; then
    echo "[netem] applying: $netem_args"
    sudo tc qdisc add dev "$IFACE" root netem $netem_args
  else
    echo "[netem] cleared (baseline)"
  fi
}

# helper: ensure cleanup on EXIT
cleanup() {
  echo "[cleanup] clearing netem and killing background processes"
  sudo tc qdisc del dev "$IFACE" root 2>/dev/null || true
  # kill any stray tcpdump
  pkill -f "tcpdump -i $IFACE udp port $SERVER_PORT" 2>/dev/null || true
}
trap cleanup EXIT

# Prepare results dir
mkdir -p "$RESULTS_DIR"

# scenarios: name -> netem args
declare -A SCENARIOS=(
  ["baseline"]=""
  ["loss_2pct"]="loss 2%"
  ["loss_5pct"]="loss 5%"
  ["delay_100ms"]="delay 100ms"
  ["jitter_10ms"]="delay 20ms 10ms"       # base 20ms with 10ms variation (jitter)
  ["duplicate_2pct"]="duplicate 2%"
  ["reorder_20pct"]="delay 10ms reorder 20%"
)

echo "[info] Running Phase-2 scenarios on interface=$IFACE, duration=${DURATION}s, clients=${NUM_CLIENTS}"

# function to run one scenario
run_scenario() {
  local scenario="$1"
  local netem_args="$2"
  local scenario_dir="$RESULTS_DIR/$scenario"

  echo
  echo "=== Scenario: $scenario (netem: ${netem_args:-none}) ==="
  mkdir -p "$scenario_dir"

  # apply netem
  apply_netem "$netem_args"

  # remove old files in repo root that server/client write
  rm -f server_positions.csv server_metrics.csv server_log.csv \
        client_display.csv client_metrics.csv client_log.csv

  # start server
  echo "[start] launching server.py"
  $PYTHON server.py > "$scenario_dir/server_stdout.txt" 2>&1 &
  SERVER_PID=$!
  sleep 1

  if ! ps -p "$SERVER_PID" >/dev/null 2>&1; then
    echo "[error] server died right after start; check $scenario_dir/server_stdout.txt"
    apply_netem ""  # clear qdisc
    return 1
  fi
  echo "[info] server pid=$SERVER_PID"

  # start tcpdump to capture scenario pcap
  echo "[start] tcpdump -> $scenario_dir/trace.pcap"
  sudo tcpdump -i "$IFACE" udp port "$SERVER_PORT" -w "$scenario_dir/trace.pcap" >/dev/null 2>&1 &
  TCPDUMP_PID=$!

  # start multiple clients in isolated working dirs
  CLIENT_PIDS=()
  CLIENT_DIRS=()
  for i in $(seq 1 "$NUM_CLIENTS"); do
    cdir="$scenario_dir/client_$i"
    mkdir -p "$cdir"
    # copy client.py (and any helper scripts) into client dir to isolate outputs
    cp client.py "$cdir/"
    # copy compute/plot scripts too so post-analysis can be run from root (we will merge later)
    # Run client from client dir so its client_display.csv and client_metrics.csv are separate
    echo "[start] launching client $i in $cdir"
    (cd "$cdir" && $PYTHON client.py > client_stdout.txt 2>&1 &) 
    pid=$!
    CLIENT_PIDS+=("$pid")
    CLIENT_DIRS+=("$cdir")
    sleep 0.2
  done

  echo "[info] All clients started: ${CLIENT_PIDS[*]}"

  # run for configured duration
  sleep "$DURATION"

  echo "[stop] killing clients and server"
  for pid in "${CLIENT_PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  kill "$SERVER_PID" 2>/dev/null || true

  # stop tcpdump
  sudo kill "$TCPDUMP_PID" 2>/dev/null || true

  # allow processes to exit
  sleep 1

  # Collect server-side files (if exist)
  [[ -f server_positions.csv ]] && mv server_positions.csv "$scenario_dir/"
  [[ -f server_metrics.csv ]] && mv server_metrics.csv "$scenario_dir/"
  [[ -f server_log.csv ]] && mv server_log.csv "$scenario_dir/"
  [[ -f server_stdout.txt ]] && mv server_stdout.txt "$scenario_dir/"

  # Collect per-client files (from client dirs)
  # move client outputs into scenario dir with client-specific names
  for idx in "${!CLIENT_DIRS[@]}"; do
    cdir="${CLIENT_DIRS[$idx]}"
    ci=$((idx+1))
    if [[ -d "$cdir" ]]; then
      [[ -f "$cdir/client_display.csv" ]] && mv "$cdir/client_display.csv" "$scenario_dir/client_${ci}_display.csv"
      [[ -f "$cdir/client_metrics.csv" ]] && mv "$cdir/client_metrics.csv" "$scenario_dir/client_${ci}_metrics.csv"
      [[ -f "$cdir/client_log.csv" ]] && mv "$cdir/client_log.csv" "$scenario_dir/client_${ci}_log.csv"
      [[ -f "$cdir/client_stdout.txt" ]] && mv "$cdir/client_stdout.txt" "$scenario_dir/client_${ci}_stdout.txt"
      # cleanup client dir
      rm -rf "$cdir"
    fi
  done

  # Merge client display files into a single client_display.csv for compute_error.py
  merged_client_display="$scenario_dir/client_display_merged.csv"
  # write header only once if files exist
  first=1
  for f in "$scenario_dir"/client_*_display.csv; do
    if [[ -f "$f" ]]; then
      if [[ $first -eq 1 ]]; then
        head -n 1 "$f" > "$merged_client_display" || true
        tail -n +2 "$f" >> "$merged_client_display" || true
        first=0
      else
        tail -n +2 "$f" >> "$merged_client_display" || true
      fi
    fi
  done

  # merge client metrics similarly
  merged_client_metrics="$scenario_dir/client_metrics_merged.csv"
  first=1
  for f in "$scenario_dir"/client_*_metrics.csv; do
    if [[ -f "$f" ]]; then
      if [[ $first -eq 1 ]]; then
        head -n 1 "$f" > "$merged_client_metrics" || true
        tail -n +2 "$f" >> "$merged_client_metrics" || true
        first=0
      else
        tail -n +2 "$f" >> "$merged_client_metrics" || true
      fi
    fi
  done

  # If compute_error.py exists in repo root, run it using the server and merged client files
  if [[ -f compute_error.py ]]; then
    echo "[analysis] Preparing files for compute_error.py"
    # compute_error.py expects server_positions.csv and client_display.csv in cwd
    # copy merged files to repo root temporarily
    if [[ -f "$scenario_dir/server_positions.csv" && -f "$merged_client_display" ]]; then
      cp "$scenario_dir/server_positions.csv" ./server_positions.csv
      cp "$merged_client_display" ./client_display.csv
      echo "[analysis] Running compute_error.py"
      $PYTHON compute_error.py
      # move generated error_results.csv into scenario dir
      [[ -f error_results.csv ]] && mv error_results.csv "$scenario_dir/"
    else
      echo "[analysis] Missing server_positions.csv or merged client display; skipping compute_error"
    fi
  else
    echo "[warn] compute_error.py not found in repo root; skipping automated error computation"
  fi

  # Run plotting if plot_error.py exists and error_results.csv produced
  if [[ -f plot_error.py && -f "$scenario_dir/error_results.csv" ]]; then
    echo "[plot] Running plot_error.py"
    # copy error_results.csv to cwd for script
    cp "$scenario_dir/error_results.csv" ./error_results.csv
    $PYTHON plot_error.py
    [[ -f error_time.png ]] && mv error_time.png "$scenario_dir/"
    [[ -f error_hist.png ]] && mv error_hist.png "$scenario_dir/"
    rm -f ./error_results.csv
  else
    echo "[plot] Skipping plotting (missing plot_error.py or error_results.csv)"
  fi

  # move merged client files into scenario dir (already there) and any server/client logs
  echo "[done] scenario $scenario finished, results saved to $scenario_dir"
  # clear netem between scenarios
  apply_netem ""
  sleep 1
}

# run all scenarios in order
for s in "${!SCENARIOS[@]}"; do
  run_scenario "$s" "${SCENARIOS[$s]}"
done

echo "=== All scenarios complete. Results under: $RESULTS_DIR ==="
