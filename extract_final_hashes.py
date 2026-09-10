"""Extract each node's final state_hash from its JSONL log on disk,
via `docker exec`, without needing to restart the cluster or modify
any running container.

Use this if your deployed main.py predates the state_hash addition to
the STATUS response -- the hash is still recoverable because state.py's
receive() has been logging "state_hash_after" on every RECEIVE_STATE
line all along.

Usage:
    python3 extract_final_hashes.py
"""

import json
import subprocess

NODE_COUNT = 10


def get_last_state_hash(node_id):
    container = f"node{node_id}"
    log_path = f"/data/node-{node_id}.jsonl"
    try:
        result = subprocess.run(
            ["docker", "exec", container, "cat", log_path],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"  [warn] could not read log from {container}: {exc.stderr.strip()}")
        return None
    except FileNotFoundError:
        print("  [error] 'docker' command not found -- run this from a shell "
              "that has Docker on PATH")
        return None

    last_hash = None
    last_calendar_size = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") == "RECEIVE_STATE" and "state_hash_after" in record:
            last_hash = record["state_hash_after"]
            last_calendar_size = record.get("calendar_size_after")

    return last_hash, last_calendar_size


def main():
    print(f"{'node':<6}{'calendar_size':<16}{'state_hash':<66}")
    results = {}
    for node_id in range(NODE_COUNT):
        outcome = get_last_state_hash(node_id)
        if outcome is None:
            print(f"{node_id:<6}{'NO DATA':<16}")
            continue
        state_hash, calendar_size = outcome
        results[node_id] = state_hash
        print(f"{node_id:<6}{str(calendar_size):<16}{state_hash}")

    print()
    hashes = set(h for h in results.values() if h)
    if len(hashes) == 1:
        print("CONVERGED: all nodes share an identical state_hash.")
    elif len(hashes) == 0:
        print("No state_hash data found in any node's log.")
    else:
        print(f"NOT CONVERGED: found {len(hashes)} distinct state_hash values.")

    with open("final_hashes_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nWritten to final_hashes_report.json")


if __name__ == "__main__":
    main()
