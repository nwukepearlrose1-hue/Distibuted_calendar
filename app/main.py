import os
import time

from .logging_utils import JsonlLogger
from .scheduler import Scheduler
from .server import NodeServer
from .state import NodeState
from .topology import get_node_address

Number_NODES = 10


def main():
    node_id = int(os.environ["NODE_ID"])
    base_seed = int(os.environ.get("BASE_RANDOM_SEED", "42"))
    min_delay = float(os.environ.get("MIN_DELAY", "30"))
    max_delay = float(os.environ.get("MAX_DELAY", "90"))
    log_directory = os.environ.get("LOG_DIRECTORY", "/data")

    os.makedirs(log_directory, exist_ok=True)
    log_path = os.path.join(log_directory, f"node-{node_id}.jsonl")

    logger = JsonlLogger(log_path)
    state = NodeState(node_id, logger)

    left_id = (node_id - 1) % Number_NODES
    right_id = (node_id + 1) % Number_NODES
    # Look up neighbors' real lab-network addresses from topology.json,
    # since Docker's internal DNS (node0, node1, ...) only resolves
    # within a single physical computer, not across the lab network.
    neighbors = [get_node_address(left_id), get_node_address(right_id)]
    print(f"[node {node_id}] neighbors resolved to: {neighbors}", flush=True)

    # The container always listens on 8000 internally -- it's the
    # docker-compose port mapping (e.g. 9000+node_id -> 8000) that
    # makes this node reachable at its topology.json port externally.
    server = NodeServer(node_id, state, port=8000)
    scheduler = Scheduler(node_id, state, neighbors, base_seed, min_delay, max_delay)

    server.final_sync_handler = scheduler.final_sync_send
    server.status_provider = lambda: {
        **state.snapshot(),
        "state_hash": state.state_hash(),
        "scheduler_done": scheduler.done.is_set(),
    }

    server.start()

    # Give every container's TCP server a moment to come up before
    # avoid burst of retries at t=0.
    time.sleep(3)

    scheduler.run()

    # Stay and answer STATUS and FINAL_SYNC requests from the
    # controller after this node's own scheduling is finished.
    while True:
        time.sleep(5)


if __name__ == "__main__":
    main()
