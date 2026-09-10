# Distributed Calendar (Vector Clock Ring) — Multi-Computer Setup

A 10-node ring topology distributed calendar system using Lamport
and vector clocks for causal ordering, with peer-to-peer TCP sync
and eventual consistency via a final synchronization phase.

Runs across **3 physical computers** on the same lab network, per
the Assignment 1.4 requirement (no `localhost` connections between
computers; nodes must use real lab IP addresses).

## Computer assignment

| Computer | Nodes | Compose file |
|---|---|---|
| Computer 1 | 0, 1, 2, 3 | `docker-compose.computer1.yml` |
| Computer 2 | 4, 5, 6 | `docker-compose.computer2.yml` |
| Computer 3 | 7, 8, 9 | `docker-compose.computer3.yml` |

## One-time setup (do this first, on ONE computer, then copy the whole folder to the other two)

1. Find each computer's real lab IP address:
   - Windows: `ipconfig` (look for IPv4 Address)
   - Linux/Mac: `ip addr` or `hostname -I`
2. Open `topology.json` and replace `COMPUTER1_IP`, `COMPUTER2_IP`,
   `COMPUTER3_IP` with the three real IP addresses.
3. Copy the **entire project folder** (with the filled-in
   `topology.json`) to all three computers — via USB drive, shared
   network folder, or `git clone` after pushing to GitHub. All three
   computers must have the exact same `topology.json`.

## Startup order

Start all three at roughly the same time (order between computers
doesn't matter, but each computer starts all its own nodes together):

```bash
# On Computer 1:
docker compose -f docker-compose.computer1.yml up --build -d

# On Computer 2:
docker compose -f docker-compose.computer2.yml up --build -d

# On Computer 3:
docker compose -f docker-compose.computer3.yml up --build -d
```

Check each computer's containers came up:
```bash
docker compose -f docker-compose.computer1.yml ps   # (swap filename per computer)
```

## Running the final-sync controller

Run this from **any one** of the three computers (it reads
`topology.json` to reach all 10 nodes over the network):

```bash
python3 final_sync_controller.py
```

This polls all 10 nodes until they finish scheduling, drives the
final-sync rounds, and reports the convergence table (lamport,
calendar_size, state_hash per node).

## Pulling logs for the reports

`docker exec`/`docker cp` only reach containers on the **local**
machine, so run this on **each** computer for its own nodes:

```bash
# Computer 1:
for i in 0 1 2 3; do docker cp node$i:/data/node-$i.jsonl .; done
# Computer 2:
for i in 4 5 6; do docker cp node$i:/data/node-$i.jsonl .; done
# Computer 3:
for i in 7 8 9; do docker cp node$i:/data/node-$i.jsonl .; done
```

Then collect all 10 `.jsonl` files onto one computer (or your laptop)
before running `aggregate_logs.py` / `causality_pairs.py`.

## Ports

Each node listens on container port 8000 internally, published
externally as `9000 + node_id` (so node 4 is reachable at
`<computer2_ip>:9004`). This mapping is defined in both
`topology.json` and each computer's compose file — they must always
agree.

## Structure

- `app/` -- the node application (state, protocol, server, scheduler, topology)
- `topology.json` -- maps every node_id to its real host:port (fill in real IPs)
- `docker-compose.computer{1,2,3}.yml` -- per-computer node subsets
- `final_sync_controller.py` -- external controller: waits for all
  nodes to finish scheduling, drives final-sync rounds, reports
  convergence
- `extract_final_hashes.py` -- fallback: pulls final state_hash
  directly from a computer's own local nodes via `docker exec`
- `aggregate_logs.py` -- merges all 10 nodes' JSONL logs into one
  chronological table sorted by Lamport timestamp
- `causality_pairs.py` -- classifies event pairs as
  BEFORE/AFTER/EQUAL/CONCURRENT using vector clocks

