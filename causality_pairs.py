"""Classify pairs of logged events as BEFORE / AFTER / EQUAL / CONCURRENT
using the project's own vector_compare.compare_vectors()"""

import argparse
import csv
import itertools
import json
import os
import random
import sys

NODE_COUNT = 10


def load_events(log_dir):
    """Pull every event that has a vector timestamp """
    
    events = []
    for node_id in range(NODE_COUNT):
        path = os.path.join(log_dir, f"node-{node_id}.jsonl")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") == "LOCAL_SCHEDULE":
                    events.append({
                        "event_id": record.get("event_id"),
                        "node_id": record.get("node_id"),
                        "vector": record.get("vector") or record.get("vector_timestamp"),
                        "lamport": record.get("lamport") or record.get("lamport_timestamp"),
                    })
    return events


def import_compare_vectors():
    
    sys.path.insert(0, os.getcwd())
    try:
        from app.vector_compare import compare_vectors
        return compare_vectors
    except ImportError:
        pass
    try:
        from vector_compare import compare_vectors
        return compare_vectors
    except ImportError:
        print("Could not import compare_vectors from app.vector_compare "
              "or vector_compare. Run this script from your project root.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=".", help="Directory containing node-*.jsonl files")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for sampling pairs")
    parser.add_argument("--sample-pairs", type=int, default=300,
                         help="How many random pairs to check before picking the best 10+")
    args = parser.parse_args()

    compare_vectors = import_compare_vectors()

    events = load_events(args.dir)
    print(f"Loaded {len(events)} events with vector timestamps.")
    if len(events) < 2:
        print("Not enough events to form pairs.")
        return

    random.seed(args.seed)
    all_pairs = list(itertools.combinations(events, 2))
    sample_size = min(args.sample_pairs, len(all_pairs))
    sampled = random.sample(all_pairs, sample_size)

    classified = []
    for a, b in sampled:
        if a["vector"] is None or b["vector"] is None:
            continue
        relationship = compare_vectors(a["vector"], b["vector"])
        classified.append({
            "event_a": a["event_id"],
            "node_a": a["node_id"],
            "event_b": b["event_id"],
            "node_b": b["node_id"],
            "relationship": relationship,
        })

    with open("causality_pairs.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["event_a", "node_a", "event_b", "node_b", "relationship"])
        writer.writeheader()
        writer.writerows(classified)
    print(f"Wrote {len(classified)} classified pairs to causality_pairs.csv")

    by_type = {"BEFORE": [], "AFTER": [], "EQUAL": [], "CONCURRENT": []}
    for row in classified:
        by_type[row["relationship"]].append(row)

    print("\nCounts across sampled pairs:")
    for rel, rows in by_type.items():
        print(f"  {rel}: {len(rows)}")

   #spec asks for 3 
    
    concurrent_diff_node = [
        r for r in by_type["CONCURRENT"] if r["node_a"] != r["node_b"]
    ]

    print("\n--- Suggested pairs for Report 2 ---")
    print("\nCONCURRENT (different nodes) -- need at least 3:")
    for r in concurrent_diff_node[:5]:
        print(f"  {r['event_a']} (node {r['node_a']})  vs  "
              f"{r['event_b']} (node {r['node_b']})  ->  CONCURRENT")
    if len(concurrent_diff_node) < 3:
        print(f"  [warn] only found {len(concurrent_diff_node)} cross-node concurrent "
              f"pairs in this sample -- rerun with a larger --sample-pairs value.")

    print("\nBEFORE / AFTER / EQUAL (a few examples):")
    for rel in ("BEFORE", "AFTER", "EQUAL"):
        for r in by_type[rel][:3]:
            print(f"  {r['event_a']} (node {r['node_a']})  vs  "
                  f"{r['event_b']} (node {r['node_b']})  ->  {rel}")


if __name__ == "__main__":
    main()
