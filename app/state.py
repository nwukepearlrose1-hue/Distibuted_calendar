
import copy
import threading

Number_NODES = 10
SLOT_MINUTES = 20
SCHEDULE_START_HOUR = 13  # 1:00 PM
NUM_SLOTS = 30  # 1:00 PM through 10:40 PM, 20-minute time increments
SIMULATION_DATE = "2030-10-01"


def slot_to_clock_string(slot_index):
    total_minutes = slot_index * SLOT_MINUTES
    hour_24 = SCHEDULE_START_HOUR + total_minutes // 60
    minute = total_minutes % 60
    period = "AM" if hour_24 < 12 else "PM"
    hour12 = hour_24 if hour_24 <= 12 else hour_24 - 12
    return f"{hour12}:{minute:02d} {period}"


def slot_to_24h_range(slot_index):
    """Return (start_time, end_time) as 24h 'HH:MM' strings, matching
    the section 5 event schema (e.g. "17:20" / "17:40")."""
    start_minutes = slot_index * SLOT_MINUTES
    end_minutes = start_minutes + SLOT_MINUTES

    def fmt(total_minutes):
        hour_24 = SCHEDULE_START_HOUR + total_minutes // 60
        minute = total_minutes % 60
        return f"{hour_24:02d}:{minute:02d}"

    return fmt(start_minutes), fmt(end_minutes)


class NodeState:
    def __init__(self, node_id, logger):
        self.node_id = node_id
        self.logger = logger
        self.lock = threading.RLock()

        self.lamport = 0
        self.vector = [0] * Number_NODES
        self.calendar = {}  # event_id
        self.events_created = 0
        self.messages_sent = 0

   
    def create_event(self, slot_index):
        with self.lock:
            self.lamport += 1
            self.vector[self.node_id] += 1

            event_number = self.events_created + 1
            event_id = f"N{self.node_id:02d}-E{event_number:02d}"
            start_time, end_time = slot_to_24h_range(slot_index)
            event = {
                "event_id": event_id,
                "creator_node": self.node_id,
                "event_number": event_number,
                "title": f"Node {self.node_id} Event {event_number}",
                "simulation_date": SIMULATION_DATE,
                "start_time": start_time,
                "end_time": end_time,
                "lamport_timestamp": self.lamport,
                "vector_timestamp": list(self.vector),
            }
            self.calendar[event_id] = event
            self.events_created += 1

            lamport_snapshot = self.lamport
            vector_snapshot = list(self.vector)

        self.logger.log(
            "LOCAL_SCHEDULE",
            {
                "node_id": self.node_id,
                "event_id": event_id,
                "start_time": start_time,
                "end_time": end_time,
                "lamport": lamport_snapshot,
                "vector": vector_snapshot,
            },
        )
        return event

   
    def prepare_send(self, final_sync=False):
        with self.lock:
            self.lamport += 1
            self.vector[self.node_id] += 1
            self.messages_sent += 1
            message_id = f"N{self.node_id:02d}-M{self.messages_sent:02d}"
            lamport_snapshot = self.lamport
            vector_snapshot = list(self.vector)
            # Deep copy while still holding the lock, then release
            # before any network I/O happens (caller's job).
            calendar_snapshot = copy.deepcopy(self.calendar)

        self.logger.log(
            "FINAL_SYNC_SEND" if final_sync else "SEND_STATE",
            {
                "node_id": self.node_id,
                "message_id": message_id,
                "lamport": lamport_snapshot,
                "vector": vector_snapshot,
                "calendar_size": len(calendar_snapshot),
            },
        )
        return message_id, lamport_snapshot, vector_snapshot, calendar_snapshot

   
    def receive(self, sender_id, message_id, sender_lamport, sender_vector, remote_calendar):
        with self.lock:
            lamport_before = self.lamport
            vector_before = list(self.vector)

            self.lamport = max(self.lamport, sender_lamport) + 1

            for i in range(Number_NODES):
                self.vector[i] = max(self.vector[i], sender_vector[i])
            self.vector[self.node_id] += 1

            added, duplicates, errors = self._merge(remote_calendar)

            lamport_after = self.lamport
            vector_after = list(self.vector)
            calendar_size_after = len(self.calendar)
            state_hash_after = self.state_hash()

        self.logger.log(
            "RECEIVE_STATE",
            {
                "node_id": self.node_id,
                "sender_node": sender_id,
                "message_id": message_id,
                "lamport_before": lamport_before,
                "received_lamport": sender_lamport,
                "lamport_after": lamport_after,
                "vector_before": vector_before,
                "received_vector": sender_vector,
                "vector_after": vector_after,
                "received_event_count": len(remote_calendar),
                "new_events_added": len(added),
                "duplicates_ignored": len(duplicates),
                "calendar_size_after": calendar_size_after,
                "state_hash_after": state_hash_after,
            },
        )
        return added, duplicates, errors


    def _merge(self, remote_calendar):
        added, duplicates, errors = [], [], []
        for event_id, remote_event in remote_calendar.items():
            if event_id not in self.calendar:
                self.calendar[event_id] = remote_event
                added.append(event_id)
            elif self.calendar[event_id] == remote_event:
                duplicates.append(event_id)
            else:
                errors.append(event_id)
                self.logger.log(
                    "ERROR",
                    {
                        "node_id": self.node_id,
                        "event_id": event_id,
                        "reason": "same event_id with conflicting content",
                    },
                )
        return added, duplicates, errors

  
    def snapshot(self):
        with self.lock:
            return {
                "node_id": self.node_id,
                "lamport": self.lamport,
                "vector": list(self.vector),
                "calendar_size": len(self.calendar),
            }

    def state_hash(self):
       
        import hashlib
        import json

        ids = sorted(self.calendar.keys())
        canonical = json.dumps([self.calendar[i] for i in ids], sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
