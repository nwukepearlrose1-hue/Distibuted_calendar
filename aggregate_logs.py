"""Aggregate all 10 nodes' JSONL logs into one chronological table,
sorted by Lamport timestamp (physical time is for human readability only, and
must never be used to determine ordering).

"""

import argparse
import csv
import glob
import json
import os

NODE_COUNT = 10

COLUMNS = [
    "lamport", "node_id", "type", "physical_time_utc",
    "event_id", "sender_node", "message_id",
    "vector", "calendar_size_after", "state_hash_after",
]


def load_all_records(log_dir):
    records = []
    for node_id in range(NODE_COUNT):
        path = os.path.join(log_dir, f"node-{node_id}.jsonl")
        if not os.path.exists(path):
            print(f"  [warn] missing log file: {path}")
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    print(f"  [warn] skipping malformed line in {path}")
                    continue
                records.append(record)
    return records


def normalize_record(record):
    """Flatten the differing fields across LOCAL_SCHEDULE / SEND_STATE /
    RECEIVE_STATE / ERROR into one common row shape for the table."""
    lamport = (
        record.get("lamport")
        or record.get("lamport_after")
        or record.get("received_lamport")
        or 0
    )
    vector = (
        record.get("vector")
        or record.get("vector_after")
        or record.get("received_vector")
        or []
    )
    return {
        "lamport": lamport,
        "node_id": record.get("node_id"),
        "type": record.get("type"),
        "physical_time_utc": record.get("physical_time_utc", ""),
        "event_id": record.get("event_id", ""),
        "sender_node": record.get("sender_node", ""),
        "message_id": record.get("message_id", ""),
        "vector": json.dumps(vector),
        "calendar_size_after": record.get("calendar_size_after", ""),
        "state_hash_after": (record.get("state_hash_after") or "")[:12],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=".", help="Directory containing node-*.jsonl files")
    args = parser.parse_args()

    print(f"Loading logs from: {os.path.abspath(args.dir)}")
    records = load_all_records(args.dir)
    print(f"Loaded {len(records)} total log entries across {NODE_COUNT} nodes.")

    rows = [normalize_record(r) for r in records]
    # Sort by Lamport timestamp, then node_id as a tiebreaker for
    # events that happen to share a Lamport value across nodes.
    rows.sort(key=lambda r: (r["lamport"], r["node_id"] if r["node_id"] is not None else -1))

    with open("aggregated_log.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to aggregated_log.csv")

    with open("aggregated_log.md", "w") as f:
        f.write("| " + " | ".join(COLUMNS) + " |\n")
        f.write("|" + "---|" * len(COLUMNS) + "\n")
        for row in rows:
            f.write("| " + " | ".join(str(row[c]) for c in COLUMNS) + " |\n")
    print("Wrote aggregated_log.md")

    type_counts = {}
    for row in rows:
        type_counts[row["type"]] = type_counts.get(row["type"], 0) + 1
    print("\nEvent type counts:")
    for t, c in sorted(type_counts.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    main()
