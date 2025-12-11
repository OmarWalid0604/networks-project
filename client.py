#!/usr/bin/env python3
import socket, struct, time, csv, os

# ======================================================
#                 PROTOCOL CONSTANTS
# ======================================================
MAGIC = b"GCL1"; VERSION = 1
MT_INIT, MT_SNAPSHOT, MT_EVENT, MT_ACK, MT_HEARTBEAT = range(5)

HDR_FMT = ">4sBBIIQH"
HDR_LEN = struct.calcsize(HDR_FMT)

SERVER_ADDR = ("127.0.0.1", 7777)
RUN_SECONDS = 10
SMOOTH = 0.35
EVENT_RTO_MS = 120
MAX_EVENT_RETRIES = 4

# ======================================================
#                 HELPER FUNCTIONS
# ======================================================
def monotonic_ms():
    return time.time_ns() // 1_000_000


def pack_header(msg_type, snapshot_id, seq_num, ts, payload):
    return struct.pack(
        HDR_FMT,
        MAGIC, VERSION, msg_type,
        snapshot_id, seq_num, ts, len(payload)
    ) + payload


def smooth_pos(old, new):
    if old is None:
        return new
    ox, oy = old
    nx, ny = new
    return (ox + SMOOTH*(nx-ox), oy + SMOOTH*(ny-oy))

# ======================================================
#                 CLIENT MAIN
# ======================================================
def main(client_name="player1"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.1)

    seq_out = 1
    last_recv = None

    # packet loss mechanism
    expected_snapshot = 1
    lost_snapshots = 0

    client_id = None
    players_raw = {}
    players_smooth = {}

    # We will open CSV files *after* we learn client_id to avoid filename collisions
    metrics_f = None
    metrics_w = None
    disp_f = None
    disp_w = None

    # --------------------------
    # SEND INIT
    # --------------------------
    init_payload = bytes([len(client_name)]) + client_name.encode()
    pkt = pack_header(MT_INIT, 0, seq_out, monotonic_ms(), init_payload)
    sock.sendto(pkt, SERVER_ADDR)
    seq_out += 1

    # Wait for ACK and client_id
    while client_id is None:
        try:
            data, _ = sock.recvfrom(2048)
        except socket.timeout:
            pkt = pack_header(MT_INIT, 0, seq_out, monotonic_ms(), init_payload)
            sock.sendto(pkt, SERVER_ADDR)
            seq_out += 1
            continue

        if len(data) < HDR_LEN:
            continue

        magic, ver, mtype, snap, seq, ser_ms, plen = struct.unpack(HDR_FMT, data[:HDR_LEN])
        if magic != MAGIC or ver != VERSION or mtype != MT_ACK:
            continue

        payload = data[HDR_LEN:HDR_LEN+plen]
        if len(payload) < 3:
            continue

        cid, x, y = struct.unpack(">BBB", payload)
        client_id = int(cid)
        players_raw[client_id] = (float(x), float(y))
        players_smooth[client_id] = (float(x), float(y))
        print(f"Connected as client {client_id} at ({x},{y})")

        # Now open per-client CSV files (safe from collisions)
        metrics_fname = f"client_metrics_{client_id}.csv"
        disp_fname = f"client_display_{client_id}.csv"

        # Ensure no leftover files with same name; open fresh
        if os.path.exists(metrics_fname):
            os.remove(metrics_fname)
        if os.path.exists(disp_fname):
            os.remove(disp_fname)

        metrics_f = open(metrics_fname, "w", newline="")
        metrics_w = csv.writer(metrics_f)
        metrics_w.writerow([
            "client_id","snapshot_id","seq_num",
            "server_timestamp_ms","recv_time_ms",
            "latency_ms","jitter_ms","lost_snapshots"
        ])
        metrics_f.flush()

        disp_f = open(disp_fname, "w", newline="")
        disp_w = csv.writer(disp_f)
        disp_w.writerow(["timestamp_ms","snapshot_id","player_id","displayed_x","displayed_y"])
        disp_f.flush()

    # EVENT RDT
    event_seq = 0
    outstanding_event = None
    next_event_time = time.time() + 2.0

    def send_critical_event(event_type, now_ms):
        nonlocal event_seq, seq_out, outstanding_event
        event_seq += 1
        payload = struct.pack(">BI", event_type, event_seq)
        pkt = pack_header(MT_EVENT, 0, seq_out, now_ms, payload)
        sock.sendto(pkt, SERVER_ADDR)
        seq_out += 1

        outstanding_event = {
            "seq": event_seq,
            "type": event_type,
            "attempts": 1,
            "last": now_ms
        }

        print(f"[EVENT] Sent event {event_type}, seq={event_seq}")

    start = time.time()
    last_applied = 0

    # =====================================================
    #            MAIN RECEIVE / UPDATE LOOP
    # =====================================================
    while time.time() - start < RUN_SECONDS:
        now_ms = monotonic_ms()

        # Receive packet
        try:
            data, _ = sock.recvfrom(4096)
            recv_ms = monotonic_ms()
        except socket.timeout:
            data = None

        if data and len(data) >= HDR_LEN:
            magic, ver, mtype, snap, seq, ser_ms, plen = struct.unpack(
                HDR_FMT, data[:HDR_LEN]
            )
            payload = data[HDR_LEN:HDR_LEN+plen]

            # --------------------------
            # SNAPSHOT PROCESSING
            # --------------------------
            if mtype == MT_SNAPSHOT:

                # ---- PACKET LOSS ESTIMATION ----
                if snap > expected_snapshot:
                    lost_here = snap - expected_snapshot
                    lost_snapshots += lost_here
                    print(f"[LOSS] {lost_here} snapshots lost before {snap} (total={lost_snapshots})")
                expected_snapshot = snap + 1

                # ---- DUPLICATE / OLD CHECK ----
                if snap <= last_applied:
                    continue

                if plen < 2:
                    continue

                (num_players,) = struct.unpack_from(">H", payload, 0)
                offset = 2

                new_positions = {}
                for _ in range(num_players):
                    if offset + 3 > len(payload):
                        break
                    pid, x, y = struct.unpack_from(">BBB", payload, offset)
                    offset += 3
                    new_positions[int(pid)] = (float(x), float(y))

                # latency & jitter
                latency = recv_ms - ser_ms
                jitter = 0 if last_recv is None else abs((recv_ms - last_recv))
                last_recv = recv_ms

                # apply smoothing
                for pid, pos in new_positions.items():
                    players_raw[pid] = pos
                for pid, raw_pos in players_raw.items():
                    old_pos = players_smooth.get(pid)
                    players_smooth[pid] = smooth_pos(old_pos, raw_pos)

                # log displayed positions
                for pid, (sx, sy) in players_smooth.items():
                    # ensure consistent primitive types
                    disp_w.writerow([int(recv_ms), int(snap), int(pid), float(sx), float(sy)])
                disp_f.flush()

                # metrics log
                metrics_w.writerow([
                    int(client_id), int(snap), int(seq),
                    int(ser_ms), int(recv_ms),
                    float(latency), float(jitter), int(lost_snapshots)
                ])
                metrics_f.flush()

                last_applied = snap
                print(f"[SNAP {snap}] latency={latency}, jitter={jitter}, lost_total={lost_snapshots}")

            # --------------------------
            # EVENT ACK
            # --------------------------
            elif mtype == MT_ACK and plen >= 4:
                (ack_seq,) = struct.unpack(">I", payload[:4])
                if outstanding_event and ack_seq == outstanding_event["seq"]:
                    print(f"[EVENT-ACK] seq={ack_seq}")
                    outstanding_event = None

        # --------------------------
        # EVENT RDT RETRANSMISSION
        # --------------------------
        if outstanding_event:
            if now_ms - outstanding_event["last"] >= EVENT_RTO_MS:
                if outstanding_event["attempts"] >= MAX_EVENT_RETRIES:
                    print(f"[EVENT] Giving up on seq={outstanding_event['seq']}")
                    outstanding_event = None
                else:
                    # retransmit
                    payload = struct.pack(">BI",
                                          outstanding_event["type"],
                                          outstanding_event["seq"])
                    pkt = pack_header(MT_EVENT, 0, seq_out, now_ms, payload)
                    sock.sendto(pkt, SERVER_ADDR)
                    seq_out += 1
                    outstanding_event["attempts"] += 1
                    outstanding_event["last"] = now_ms
                    print(f"[EVENT] Retransmit seq={outstanding_event['seq']} attempt {outstanding_event['attempts']}")

        # --------------------------
        # GENERATE NEXT CRITICAL EVENT
        # --------------------------
        if outstanding_event is None and time.time() >= next_event_time:
            send_critical_event(event_type=2, now_ms=now_ms)
            next_event_time = time.time() + 1.5

    # Cleanup
    if metrics_f:
        metrics_f.close()
    if disp_f:
        disp_f.close()
    sock.close()
    print("Client finished.")

if __name__ == "__main__":
    main("player1")
