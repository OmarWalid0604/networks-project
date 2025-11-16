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
        f.flush()  # Force write headers immediately
        
        # Keep running for at least 10 seconds
        start_time = time.time()
        while time.time() - start_time < 10:
            try:
                data, _ = sock.recvfrom(2048)
                recv_ms = monotonic_ms()
                if len(data) < HDR_LEN: 
                    continue
                magic, ver, mtype, snap, seq, ser_ms, plen = struct.unpack(HDR_FMT, data[:HDR_LEN])
                if magic != MAGIC or ver != VERSION:
                    continue
                # Parse payload
                latency = recv_ms - ser_ms
                client_id = 0
                if mtype == MT_ACK and plen >= 6:
                    client_id = struct.unpack(">I", data[HDR_LEN:HDR_LEN+4])[0]
                w.writerow([client_id, snap, seq, ser_ms, recv_ms, latency])
                f.flush()  # Force write each row immediately
            except socket.timeout:
                continue  # Keep looping even on timeout

if __name__ == "__main__":
    print("Client starting →", SERVER_ADDR)
    main("player1")
