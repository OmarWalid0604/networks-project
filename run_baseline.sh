set -euo pipefail

# Clean old logs
rm -f server_log.csv client_log.csv

# Start server
python3 server.py > /dev/null 2>&1 &
SERVER_PID=$!
sleep 0.5

# Start one client (you can add more clients in new shells if desired)
python3 client.py > /dev/null 2>&1 &
CLIENT_PID=$!

# Run baseline for ~5 seconds
sleep 5

# Stop processes
kill $CLIENT_PID || true
kill $SERVER_PID || true
wait || true

echo "=== Baseline complete ==="
ls -l server_log.csv client_log.csv