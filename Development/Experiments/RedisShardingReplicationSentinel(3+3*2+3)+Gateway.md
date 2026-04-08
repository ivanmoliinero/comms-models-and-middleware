---
experiment: RedisShardingReplicationSentinel(3+3*2+3)-Gateway
improves: "[[Development/Experiments/RedisShardingSentinel-Gateway|RedisShardingSentinel-Gateway]]"
---

> [!warning]
> This experiment has been performed under lab conditions, so bear in mind that **resource limits** have been applied to every component if it.

# Other preparations
Same as [[Development/Experiments/Redis-OpenResty|Redis-OpenResty]].

# Redis
Same process as [[Development/Experiments/RedisShardingSentinel-Gateway#Redis|RedisShardingSentinel-Gateway#Redis]], but changing the `deploy.sh` by [[software-testing/redisShardingReplicationSentinel-gateway/redis/deploy.sh]].

In this case we will have the following instances running in this experiment:
- 3 masters: master-a, master-b, master-c
- 6 replicas: replica-a1, replica-a2, replica-b1, replica-b2, replica-c1, replica-c2
- 3 sentinels: sentinel-1, sentinel-2, sentinel-3

# Gateway
Same as [[Development/Experiments/RedisShardingSentinel-Gateway#Gateway|RedisShardingSentinel-Gateway#Gateway]].

# Checks
## check:: Basic purchase

1. Perform a request
```bash
# client 1: first purchase
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-001"
# output
{"processed_by":"shard-c","ticket_number":9999,"status":"success","node_ip":"172.19.0.4"}
# ------------------------------------------------------------------------------
# client 1: retry
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-001"
# output
{"message":"Ticket already purchased with this ID","status":"error","processed_by":"shard-c"}
# ------------------------------------------------------------------------------
```

This is the expected behavior.
## check:: No replication acknowledgement

We will simulate a replication acknowledgement timeout by incrementally pausing *C-replicas*.

```bash
docker pause replica-c1
```

```bash
# client 2: first purchase
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-002"
# output
{"processed_by":"shard-c","ticket_number":9998,"status":"success","node_ip":"172.19.0.4"}
# ------------------------------------------------------------------------------
# client 2: retry
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-002"
# output
{"message":"Ticket already purchased with this ID","status":"error","processed_by":"shard-c"}
# ------------------------------------------------------------------------------
```

This is expected since we still have another replica for *master-c*, let's test what happens when it runs out of replicas.

```bash
docker pause replica-c2
```

```bash
# client 3: first purchase
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-003"
# output
{"error":"Replication timeout. Purchase rolled back."}
# ------------------------------------------------------------------------------
# client 3: retry
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-003"
# output
{"error":"Replication timeout. Purchase rolled back."}
# ------------------------------------------------------------------------------
```

This is absolutely the expected behavior.

Now let's check the system successfully includes again the unpaused replicas.

```bash
docker unpasuse replica-c1 replica-c2
```

```bash
# client 3: first purchase
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-003"
# output
{"processed_by":"shard-c","ticket_number":9997,"status":"success","node_ip":"172.19.0.4"}
# ------------------------------------------------------------------------------
# client 3: retry
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-003"
# output
{"message":"Ticket already purchased with this ID","status":"error","processed_by":"shard-c"}
# ------------------------------------------------------------------------------
```

This is the expected.
## check:: Gateway's correct identification of the new master

In this test we will be testing the gateway's logic in charge of spotting the right Redis server to talk to. We will force `master-c` to fall and the client requesting will be *client 1*.

> [!warning] Remember
> - Flush the *master-c* data before executing the following requests. You can do it with:
> ```redis-cli
> FLUSHALL
> SET tickets-counter 10000
> ```
> - Unpause the two replicas *replica-c1* and *replica-c2*.


```bash
docker pause master-c
```

```bash
# client 2: first purchase
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-002"
# output
{"processed_by":"shard-c","ticket_number":9999,"status":"success","node_ip":"172.19.0.9"}
# ------------------------------------------------------------------------------
```

As we discussed in [[Development/Experiments/RedisShardingSentinel-Gateway#check Gateway's correct identification of the new master]], this is the expected and desired behavior of the system.