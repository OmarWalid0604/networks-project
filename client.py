import socket, struct, time, csv

MAGIC = b"GCL1"; VERSION = 1
MT_INIT, MT_SNAPSHOT, MT_EVENT, MT_ACK, MT_HEARTBEAT = range(5)
HDR_FMT = ">4sBBIIQH"
HDR_LEN = struct.calcsize(HDR_FMT)
SERVER_ADDR = ("127.0.0.1", 7777)

def monotonic_ms():
    return time.monotonic_ns() // 1_000_000

def pack_header(msg_type, snapshot_id, seq_num, server_ts_ms, payload):
    return struct.pack(HDR_FMT, MAGIC, VERSION, msg_type, snapshot_id, seq_num,
                       server_ts_ms, len(payload)) + payload

def main(client_name="player"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)

    # INIT
    payload = bytes([len(client_name)]) + client_name.encode("utf-8")
    pkt = pack_header(MT_INIT, 0, 1, monotonic_ms(), payload)
    sock.sendto(pkt, SERVER_ADDR)

    # Expect ACK then SNAPSHOTs
    with open("client_log.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["client_id","snapshot_id","seq_num","server_timestamp_ms",
                    "recv_time_ms","latency_ms"])
        while True:
            data, _ = sock.recvfrom(2048)
            recv_ms = monotonic_ms()
            if len(data) < HDR_LEN: 
                continue
            magic, ver, mtype, snap, seq, ser_ms, plen = struct.unpack(HDR_FMT, data[:HDR_LEN])
            if magic != MAGIC or ver != VERSION:
                continue
            # (Optional) parse payload
            latency = recv_ms - ser_ms
            client_id = 0
            if mtype == MT_ACK and plen >= 6:
                client_id = struct.unpack(">I", data[HDR_LEN:HDR_LEN+4])[0]
            w.writerow([client_id, snap, seq, ser_ms, recv_ms, latency])

if __name__ == "__main__":
    print("Client starting ->", SERVER_ADDR)
    main("player1")