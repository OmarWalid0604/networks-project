#!/usr/bin/env bash
set -x  # Show all commands
set -euo pipefail

echo "=== Script starting in directory: $(pwd) ==="

# Clean old logs
rm -f server_log.csv client_log.csv

# Start server
echo "=== Starting server ==="
python3 server.py &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Check if server started
sleep 2
if ps -p $SERVER_PID > /dev/null; then
    echo "Server is running"
else
    echo "ERROR: Server died!"
    exit 1
fi

# Start client
echo "=== Starting client ==="
python3 client.py &
CLIENT_PID=$!
echo "Client PID: $CLIENT_PID"

# Run baseline for ~10 seconds
echo "=== Waiting 10 seconds ==="
sleep 10

# Check processes before killing
echo "=== Checking processes ==="
ps aux | grep python || true

# Stop processes
echo "=== Stopping processes ==="
kill $CLIENT_PID 2>/dev/null || echo "Client already stopped"
kill $SERVER_PID 2>/dev/null || echo "Server already stopped"
wait 2>/dev/null || true

echo "=== Baseline complete ==="
echo "=== Files in current directory ==="
ls -la
echo "=== Looking for CSV files ==="
ls -l *.csv 2>/dev/null || echo "No CSV files found"
