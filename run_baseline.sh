set -euo pipefail

# Clean old logs
rm -f server_log.csv client_log.csv

# Start server
python3 server.py &
SERVER_PID=$!
sleep 2

# Start one client 
python3 client.py &
CLIENT_PID=$!

# Run baseline for ~5 seconds
sleep 10

# Stop processes
kill $CLIENT_PID 2>/dev/null || true
kill $SERVER_PID 2>/dev/null || true
wait 2>/dev/null || true

echo "=== Baseline complete ==="
ls -l server_log.csv client_log.csv 2>/dev/null || echo "CSV files not found"
