with open("server_log.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["client_id","snapshot_id","seq_num","server_timestamp_ms",
                    "recv_time_ms","latency_ms"])
        f.flush()  # Add this

        def recv_loop():
            nonlocal w
            while True:
                try:
                    data, addr = sock.recvfrom(2048)
                except socket.timeout:
                    continue
                recv_ms = monotonic_ms()
                if len(data) < HDR_LEN:
                    continue
                magic, ver, mtype, snap, seq, ser_ms, plen = struct.unpack(HDR_FMT, data[:HDR_LEN])
                if magic != MAGIC or ver != VERSION: 
                    continue
                payload = data[HDR_LEN:HDR_LEN+plen]

                if addr not in clients and mtype == MT_INIT:
                    clients[addr] = next_client_id; next_client_id += 1
                    seq_nums[addr] = 1
                    cid = clients[addr]
                    # INIT-ACK payload: client_id(4), grid_n(2)
                    pay = struct.pack(">IH", cid, GRID_N)
                    pkt = pack_header(MT_ACK, 0, seq_nums[addr], monotonic_ms(), pay)
                    sock.sendto(pkt, addr)
                elif mtype == MT_EVENT and addr in clients:
                    # Minimal event handling omitted for Phase 1
                    pass

                # log latency wrt server_timestamp_ms in header
                cid = clients.get(addr, 0)
                latency = recv_ms - ser_ms
                w.writerow([cid, snap, seq, ser_ms, recv_ms, latency])
                f.flush()  # Add this to force write immediately
