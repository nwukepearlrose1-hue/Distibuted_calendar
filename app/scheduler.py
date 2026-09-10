"""Background scheduler thread for one node.


"""

import random
import threading
import time

from . import protocol
from .state import NUM_SLOTS

TOTAL_EVENTS = 10

#create scheduler 

class Scheduler:
    def __init__(self, node_id, state, neighbors, base_seed, min_delay=30, max_delay=90):
        self.node_id = node_id
        self.state = state
        self.neighbors = neighbors  # (host, port) tuples w length 2
        self.rng = random.Random(base_seed + node_id)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.done = threading.Event()

    def run(self):
        available_slots = list(range(NUM_SLOTS))
        self.rng.shuffle(available_slots)
        chosen_slots = available_slots[:TOTAL_EVENTS]

        for slot in chosen_slots:
            delay = self.rng.uniform(self.min_delay, self.max_delay)
            time.sleep(delay)
            self.state.create_event(slot)
            self.send_to_neighbors()

        self.done.set()

    def send_to_neighbors(self, final_sync=False):
        for host, port in self.neighbors:
            message_id, lamport, vector, calendar = self.state.prepare_send(
                final_sync=final_sync
            )
            message = {
                "type": "SYNC",
                "sender_id": self.node_id,
                "message_id": message_id,
                "lamport": lamport,
                "vector": vector,
                "calendar": calendar,
            }
            try:
                protocol.send_message(host, port, message)
            except ConnectionError:
                pass

    def final_sync_send(self):
        self.send_to_neighbors(final_sync=True)
