#!/usr/bin/env python3
import socket, struct, time, csv, threading

MAGIC = b"GCL1"; VERSION = 1
MT_INIT, MT_SNAPSHOT, MT_EVENT, MT_ACK, MT_HEARTBEAT = range(5)
HDR_FMT = ">4sBBIIQH"
HDR_LEN = struct.calcsize(HDR_FMT)

GRID_N = 20
TICK_HZ = 20
SERVER_ADDR = ("127.0.0.1", 7777)

clients = {}
seq_nums = {}
next_client_id = 1
snapshot_id = 0
grid_owner = [[0]*GRID_N for _ in range(GRID_N)]

def monotonic_ms():
    return time.monotonic_ns() // 1_000_000

def pack_header(msg_type, snapshot_id, seq_num, server_ts_ms, payload):
    payload_len = len(payload)
    return struct.pack(HDR_FMT, MAGIC, VERSION, msg_type,
                       snapshot_id, seq_num, server_ts_ms,
                       payload_len) + payload

def run_server():
    global next_client_id, snapshot_id, seq_nums
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(SERVER_ADDR)
    sock.settimeout(0.001)

    f = open("server_log.csv", "w", newline="")  # ← CHANGED: moved outside with
    w = csv.writer(f)
    w.writerow(["client_id","snapshot_id","seq_num",
                "server_timestamp_ms","recv_time_ms","latency_ms"])
    f.flush()

    def recv_loop():
        global next_client_id, seq_nums
        while True:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            recv_ms = monotonic_ms()
            if len(data) < HDR_LEN:
                continue
            magic, ver, mtype, snap, seq, ser_ms, plen = struct.unpack(
                HDR_FMT, data[:HDR_LEN]
            )
            if magic != MAGIC or ver != VERSION:
                continue

            if addr not in clients and mtype == MT_INIT:
                clients[addr] = next_client_id
                seq_nums[addr] = 1
                cid = next_client_id
                next_client_id += 1
                payload = struct.pack(">IH", cid, GRID_N)
                pkt = pack_header(MT_ACK, 0, seq_nums[addr],
                                  monotonic_ms(), payload)
                sock.sendto(pkt, addr)

            cid = clients.get(addr, 0)
            latency = recv_ms - ser_ms
            w.writerow([cid, snap, seq, ser_ms, recv_ms, latency])
            f.flush()

    threading.Thread(target=recv_loop, daemon=True).start()
    print(f"Server on {SERVER_ADDR}")

    try:  # ← CHANGED: added try-finally to close file
        while True:
            time.sleep(1.0 / TICK_HZ)
            snapshot_id += 1
            server_ms = monotonic_ms()
            payload = struct.pack(">H", 0)
            for addr in list(clients.keys()):
                seq_nums[addr] += 1
                pkt = pack_header(MT_SNAPSHOT, snapshot_id,
                                  seq_nums[addr], server_ms, payload)
                sock.sendto(pkt, addr)
    finally:
        f.close()  # ← CHANGED: ensure file is closed

if __name__ == "__main__":
    run_server()
