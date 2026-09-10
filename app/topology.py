"""Loads topology.json, which maps every node_id to the real lab
network host:port it's reachable at. This replaces Docker's internal
DNS (node0, node1, ...) which only works within a single Docker host
-- across physical computers, nodes need real IP addresses.
"""

import json
import os

# topology.json lives at the project root, one level up from app/
_TOPOLOGY_PATH = os.environ.get(
    "TOPOLOGY_PATH",
    os.path.join(os.path.dirname(__file__), "..", "topology.json"),
)


def load_topology():
    with open(_TOPOLOGY_PATH) as f:
        raw = json.load(f)
    # Drop the human-readable comment key, keep only real node entries
    return {
        int(node_id): entry
        for node_id, entry in raw.items()
        if node_id != "_comment"
    }


def get_node_address(node_id):
    """Return (host, port) for the given node_id, as recorded in
    topology.json."""
    topology = load_topology()
    if node_id not in topology:
        raise KeyError(
            f"node_id {node_id} not found in topology.json -- "
            f"check that the file lists all 10 nodes (0-9)."
        )
    entry = topology[node_id]
    host = entry["host"]
    if host.startswith("COMPUTER") and host.endswith("_IP"):
        raise ValueError(
            f"topology.json still has a placeholder host ('{host}') for "
            f"node {node_id} -- replace it with a real lab IP address "
            f"before starting the cluster."
        )
    return host, entry["port"]
