#!/usr/bin/env bash
set -euo pipefail

# ========================
# CONFIGURATION
# ========================
IFACE="${IFACE:-lo}"          # Linux loopback interface
DURATION="${DURATION:-15}"    # Time per scenario
CLIENTS="${CLIENTS:-2}"       # Number of clients per scenario
RESULTS_ROOT="results_phase2"
PORT=7777                     # Server port

mkdir -p "$RESULTS_ROOT"

echo "[info] Running Phase-2 scenarios on interface=$IFACE, duration=${DURATION}s, clients=$CLIENTS"


# ========================
# APPLY NETEM HELPER
# ========================
apply_netem() {
    local args="${1:-}"

    sudo tc qdisc del dev "$IFACE" root 2>/dev/null || true

    if [[ -n "$args" ]]; then
        echo "[netem] applying: $args"
        sudo tc qdisc add dev "$IFACE" root netem $args
    else
        echo "[netem] clearing (baseline)"
    fi
}


# ========================
# RUN A SINGLE SCENARIO
# ========================
run_scenario() {
    local NAME="$1"
    local NETEM="$2"

    echo
    echo "=== Scenario: $NAME (netem: ${NETEM:-none}) ==="
    local OUT_DIR="$RESULTS_ROOT/$NAME"
    mkdir -p "$OUT_DIR"

    # Apply netem
    apply_netem "$NETEM"

    # Start server
    echo "[start] launching server.py"
    python3 server.py > "$OUT_DIR/server_output.txt" 2>&1 &
    SERVER_PID=$!
    echo "[info] server pid=$SERVER_PID"

    sleep 2

    # Start tcpdump
    echo "[start] tcpdump -> $OUT_DIR/trace.pcap"
    sudo tcpdump -i "$IFACE" udp port $PORT -w "$OUT_DIR/trace.pcap" >/dev/null 2>&1 &
    TCPDUMP_PID=$!

    # Start clients
    echo "[start] launching $CLIENTS clients"
    CLIENT_PIDS=""
    for i in $(seq 1 $CLIENTS); do
        C_DIR="$OUT_DIR/client_$i"
        mkdir -p "$C_DIR"

        python3 client.py \
            > "$C_DIR/client_output.txt" 2>&1 &

        PID=$!
        CLIENT_PIDS="$CLIENT_PIDS $PID"
        echo "[start] launching client $i in $C_DIR"
    done

    echo "[info] All clients started: $CLIENT_PIDS"

    # Run for duration
    sleep "$DURATION"

    # ========================
    # STOP PROCESSES
    # ========================
    echo "[stop] killing clients and server"

    for PID in $CLIENT_PIDS; do
        kill "$PID" 2>/dev/null || true
    done

    kill "$SERVER_PID" 2>/dev/null || true

    sudo kill "$TCPDUMP_PID" 2>/dev/null || true
    sleep 2


    # ========================
    # PROCESSING: COPY LOGS
    # ========================
    cp server_positions.csv "$OUT_DIR/server_positions.csv" 2>/dev/null || true
    cp server_metrics.csv "$OUT_DIR/server_metrics.csv" 2>/dev/null || true

    for i in $(seq 1 $CLIENTS); do
        C_DIR="$OUT_DIR/client_$i"
        cp client_display.csv "$C_DIR/client_display.csv" 2>/dev/null || true
        cp client_metrics.csv "$C_DIR/client_metrics.csv" 2>/dev/null || true
    done


    # ========================
    # PCAP → TEXT (Tshark export)
    # ========================
    if command -v tshark >/dev/null 2>&1; then
        echo "[pcap] exporting text logs via tshark"

        tshark -r "$OUT_DIR/trace.pcap" \
            > "$OUT_DIR/trace_parsed.txt" 2>/dev/null || true

        tshark -r "$OUT_DIR/trace_pcap" -T fields \
            -e frame.number -e frame.time_epoch -e ip.src -e ip.dst \
            -e udp.srcport -e udp.dstport -e frame.len \
            > "$OUT_DIR/trace_summary.csv" 2>/dev/null || true
    fi


    # ========================
    # ERROR CALCULATION
    # ========================
    echo "[analysis] Running compute_error.py for all clients"

    for i in $(seq 1 $CLIENTS); do
        C_DIR="$OUT_DIR/client_$i"

        if [[ -f "$C_DIR/client_display.csv" ]]; then
            python3 compute_error.py \
                --server "$OUT_DIR/server_positions.csv" \
                --client "$C_DIR/client_display.csv" \
                --out_csv "$OUT_DIR/error_client${i}.csv" \
                --out_plot "$OUT_DIR/plots_client${i}" \
                || echo "[warn] compute_error.py failed for client $i"
        else
            echo "[warn] missing $C_DIR/client_display.csv"
        fi
    done


    echo "[done] scenario $NAME finished"
}


# ========================
# SCENARIOS
# ========================
run_scenario "baseline" ""
run_scenario "loss_2pct" "loss 2%"
run_scenario "loss_5pct" "loss 5%"
run_scenario "delay_100ms" "delay 100ms"
run_scenario "jitter_10ms" "delay 20ms 10ms"
run_scenario "reorder_20pct" "delay 10ms reorder 20%"
run_scenario "duplicate_5pct" "duplicate 5%"

# Clear netem
echo "[cleanup] clearing netem and killing background processes"
apply_netem ""
