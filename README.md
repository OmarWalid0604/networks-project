*Requirements*

* Python 3.10+ (stdlib only).
* Runs on Linux/macOS/Windows. For grading on Linux, later tests can use tc netem to add delay/loss. ([man7.org][3])

*Run locally (baseline)*

bash
# terminal 1
python3 server.py

# terminal 2
python3 client.py


*Outputs*

* server_log.csv, client_log.csv with:
  client_id, snapshot_id, seq_num, server_timestamp_ms, recv_time_ms, latency_ms

*Notes for future phases*

* To emulate impairments on Linux:
  sudo tc qdisc add dev <IFACE> root netem loss 2% or delay 100ms etc. Remove with sudo tc qdisc del dev <IFACE> root. See tc-netem(8) manual. ([man7.org][3])
* To capture packets for plots: tshark -i <IFACE> -w run.pcapng and filter later with tshark -r run.pcapng -Y 'udp.port==7777'. ([Wireshark][6])

---
