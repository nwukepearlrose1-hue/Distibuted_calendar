

import json
import math
import os
import socket
import sys
import time

NODE_COUNT = 10
TOPOLOGY_PATH = os.environ.get("TOPOLOGY_PATH", "topology.json")

POLL_INTERVAL_SECONDS = 5
MAX_WAIT_SECONDS = 60 * 60  # give up after 1 hour if something's stuck
SETTLE_SECONDS_BETWEEN_ROUNDS = 2
FINAL_SYNC_ROUNDS = math.ceil(NODE_COUNT / 2)  # 5 for a 10-node ring


def load_topology():
    with open(TOPOLOGY_PATH) as f:
        raw = json.load(f)
    topology = {
        int(node_id): entry for node_id, entry in raw.items() if node_id != "_comment"
    }
    for node_id, entry in topology.items():
        if entry["host"].startswith("COMPUTER") and entry["host"].endswith("_IP"):
            print(f"[error] topology.json still has a placeholder host for node "
                  f"{node_id} -- fill in real lab IPs before running this.")
            sys.exit(1)
    return topology


TOPOLOGY = load_topology()


def node_address(node_id):
    entry = TOPOLOGY[node_id]
    return entry["host"], entry["port"]


def send_and_wait(node_id, message, timeout=5):
    """Send one JSON message to a node and wait for its one-line
    JSON reply. 
    
    Returns None on any connection error."""
    
    host, port = node_address(node_id)
    data = (json.dumps(message) + "\n").encode("utf-8")
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(data)
            sock.settimeout(timeout)
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
        if not buf:
            return None
        return json.loads(buf.decode("utf-8"))
    except OSError as exc:
        print(f"  [warn] node{node_id} unreachable at {host}:{port}: {exc}")
        return None


def get_status(node_id):
    return send_and_wait(node_id, {"type": "STATUS"})


def trigger_final_sync(node_id):
    return send_and_wait(node_id, {"type": "FINAL_SYNC"})


def wait_for_all_scheduled():
    print(f"Waiting for all {NODE_COUNT} nodes to finish scheduling...")
    start = time.time()
    known_done = set()

    while True:
        for node_id in range(NODE_COUNT):
            if node_id in known_done:
                continue  # already confirmed done, no need to keep polling it
            status = get_status(node_id)
            if status and status.get("scheduler_done"):
                known_done.add(node_id)

        print(f"  {len(known_done)}/{NODE_COUNT} nodes done "
              f"({int(time.time() - start)}s elapsed)")

        if len(known_done) == NODE_COUNT:
            print("All nodes finished scheduling.\n")
            return

        if time.time() - start > MAX_WAIT_SECONDS:
            still_waiting = [n for n in range(NODE_COUNT) if n not in known_done]
            print(f"Timed out waiting for nodes: {still_waiting}")
            sys.exit(1)

        time.sleep(POLL_INTERVAL_SECONDS)


def run_final_sync_rounds():
    print(f"Running {FINAL_SYNC_ROUNDS} final-sync rounds "
          f"(ring diameter for {NODE_COUNT} nodes)...")
    for round_num in range(1, FINAL_SYNC_ROUNDS + 1):
        print(f"  round {round_num}/{FINAL_SYNC_ROUNDS}")
        for node_id in range(NODE_COUNT):
            ack = trigger_final_sync(node_id)
            if not ack or ack.get("type") != "FINAL_SYNC_ACK":
                print(f"    [warn] node{node_id} did not ack final sync")
        
        time.sleep(SETTLE_SECONDS_BETWEEN_ROUNDS)
    print("Final-sync rounds complete.\n")


def collect_final_report():
    print("Collecting final status from all nodes...")
    report = {}
    for node_id in range(NODE_COUNT):
        status = get_status(node_id)
        report[node_id] = status

    print()
    print(f"{'node':<6}{'lamport':<10}{'calendar_size':<16}{'state_hash':<20}")
    for node_id in range(NODE_COUNT):
        s = report.get(node_id)
        if not s:
            print(f"{node_id:<6}{'UNREACHABLE':<10}")
            continue
        short_hash = s.get("state_hash", "")[:12]
        print(f"{node_id:<6}{s['lamport']:<10}{s['calendar_size']:<16}{short_hash:<20}")

    hashes = {report[n]["state_hash"] for n in report if report.get(n)}
    print()
    if len(hashes) == 1:
        print("CONVERGED: all reachable nodes share an identical state_hash.")
    else:
        print(f"NOT CONVERGED: found {len(hashes)} distinct state_hash values. "
              f"Consider running more final-sync rounds.")

    with open("final_status_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\nFull report written to final_status_report.json")


def main():
    wait_for_all_scheduled()
    run_final_sync_rounds()
    collect_final_report()


if __name__ == "__main__":
    main()
