# High availability and replication

| Topology | Failover | Data loss on failover | Notes |
|---|---|---|---|
| Single instance + backups | restore (RTO = restore time) | since last backup/WAL | fine for small/internal systems when RTO allows |
| Primary + async replica(s) | promote replica (manual or managed/automatic: Patroni, orchestrator, cloud) | replication lag at failure | most common; monitor lag |
| Primary + sync/semi-sync replica | promote | ~0 | write latency + availability trade-off |
| MongoDB replica set (≥ 3 voting members) | automatic election | 0 with `w: majority` | odd number of voters; arbiters discouraged |
| Distributed SQL / quorum stores | automatic per range | 0 with quorum writes | latency per write; multi-zone by design |

Checklist: failover tested (drill), clients reconnect (DNS/endpoint, driver retry settings), replicas in
another zone, lag alert, split-brain protection, backups taken from a replica where supported, read routing
excludes read-your-writes flows.
