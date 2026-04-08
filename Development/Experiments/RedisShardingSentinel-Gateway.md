---
experiment: RedisShardingSentinel-Gateway
---
# Brief

In this experiment we will put to the test **self-healing** for the Redis shards.

> [!warning]
> This experiment has been performed under lab conditions, so bear in mind that **resource limits** have been applied to every component if it.

# Other preparations
Same as [[Development/Experiments/Redis-OpenResty|Redis-OpenResty]].

# Redis
To implement **self-healing** in Redis we could use **sentinels**. **Sentinels** monitor the Redis instances, if any is detected as dead, they perform an action in consequence. In this case, the action to be performed is to promote a replica to master.

> [!cite]
> "*At least 3 Sentinel instances are recommended for a robust deployment.*"
> 
> source:: https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/#fundamental-things-to-know-about-sentinel-before-deploying

We will have the following instances running in this experiment:
- 3 masters: master-a, master-b, master-c
- 3 replicas: replica-a, replica-b, replica-c
- 3 sentinels: sentinel-1, sentinel-2, sentinel-3

1. Since we have a lot to initiate, the following script performs all the setup for Redis in this experiment, apart from the initialization of the state of each master (i.e. `SET tickets-counter <total-tickets / num-masters>`): [[software-testing/redisShardingSentinel-gatewaysCluster-loadBalancer/redis/deploy.sh]].

2. Initialize the state of the database.
```bash
for shard in master-a master-b master-c; do
  cat << 'EOF' | sudo docker exec -i $shard redis-cli -x FUNCTION LOAD REPLACE
#!lua name=ticket_sales
redis.register_function('buy_ticket', function(keys, args)
  if redis.call('SISMEMBER', keys[1], args[1]) == 1 then
    return -1
  else
    local ticket_number = tonumber(redis.call('DECR', keys[2]))
    if ticket_number < 0 then
      return -2
    else
      redis.call('SADD', keys[1], args[1])
      return ticket_number
    end
  end
end)
redis.register_function('rollback_ticket', function(keys, args)
  if redis.call('SREM', keys[1], args[1]) == 1 then
    return redis.call('INCR', keys[2])
  end
  return 0
end)
EOF
  sudo docker exec $shard redis-cli SET tickets-counter 10000 > /dev/null
  echo "$shard initialized."
done
```

This script sets the `tickets-counter` of each master to 10000 (for a total of 30000 tickets). It also loads both functions `buy_ticket` and `rollback_ticket` to each master.

## check:: Replication

Check that the `tickets-counter` value is also found in the replicas.
## check:: Failover correctness

Apart from the behavior check we will perform, to see the logs it's also interesting. This can be done by executing:

```bash
docker logs -f sentinel-1
```

Looking the *sentinel-1*'s logs it's enough.

We will now **simulate a failover** by pausing a master, in this case, *master-a*.

1. Pause *master-a*.
```bash
docker pause master-a
```

After 3 seconds, the log should show some movements. Precisely, we are looking for
- `+sdown master shard-a 172.19.0.2 6379`
- `+odown master shard-a 172.19.0.2 6379 #quorum 3/2`
- `+switch-master shard-a 172.19.0.2 6379 172.19.0.5 6379`

> [!warning]
> Don't panic if the log keeps printing `+switch-master shard-a 172.19.0.2 6379 172.19.0.5 6379` indefinitely, it is the expected behavior if you **stopped** the container instead of **pausing** it (Docker's DNS reasons).

# Gateway

We must do some changes to the gateway. It originally was asking to resolve the master's domain name, but now the master can change, so it the gateway has to ask a sentinel first. One important think to mention is that we cannot rely on asking to a single sentinel; if one fails, we must ask to another, and so on.

The new `nginx.conf` file is [[software-testing/redisShardingSentinel-gateways/gateway/nginx.conf]].

1. Spin up the gateway's container.
```bash
docker run -d \
  --name openresty-gateway \
  --network redis-test-net \
  -p 8080:80 \
  -v $(pwd)/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro \
  openresty/openresty:latest
```

> [!important]
> The previous command must be run from the path that contains the [[software-testing/redisShardingSentinel-gateways/gateway/nginx.conf]] file.

# Checks

## check:: Basic purchase

1. Perform a request
```bash
# client 1: first purchase
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-001"
# output
{"node_ip":"172.19.0.4","ticket_number":9999,"status":"success","processed_by":"shard-c"}
# ------------------------------------------------------------------------------
# client 1: retry
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-001"
# output
{"message":"Ticket already purchased with this ID","status":"error","processed_by":"shard-c"}
# ------------------------------------------------------------------------------
```

This is the expected behavior.
## check:: No replication acknowledgement

We will simulate a replication acknowledgement timeout by pausing `replica-c` for the *client 2*.

```bash
docker pause replica-c
```

```bash
# client 2: first purchase
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-002"
# output
{"error":"Replication timeout. Purchase rolled back."}
# ------------------------------------------------------------------------------
# client 2: retry
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-002"
# output
{"error":"Replication timeout. Purchase rolled back."}
# ------------------------------------------------------------------------------
```

Note that we requested 2 times since we recently fixed an error related with this case ([[Development/Experiments/RedisReplication-GatewayWAIT#Gateway|RedisReplication-GatewayWAIT#Gateway]]).

## check:: Gateway's correct identification of the new master

In this test we will be testing the gateway's logic in charge of spotting the right Redis server to talk to. We will force `master-c` to fall and the client requesting will be *client 1*.

> [!warning] Remember
> Remember to flush the *master-c* data before executing the following requests. You can do it with:
> ```redis-cli
> FLUSHALL
> SET tickets-counter 10000
> ```


```bash
docker pause master-c
```

```bash
# client 2: first purchase
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-002"
# output
{"error":"Replication timeout. Purchase rolled back."}
# ------------------------------------------------------------------------------
```

This is totally expected since the new master has no replica:
- The *master-c* shot down.
- The *replica-c* was promoted to be the master of *shard-c*.
- The *replica-c* (now the master) is working without a replica.

, but this is also undesired, since we created replicas to enforce availability.

To proof this is the cause of the problem, just *unpause* the *master-c*:
```bash
docker unpause master-c
```

, and then perform the request again (waiting a few seconds to let the system update its state):

```bash
# client 2: retry
curl -i "http://localhost:8080/buy?ticket_id=chaos-test-002"
# output
{"node_ip":"172.19.0.7","ticket_number":9999,"status":"success","processed_by":"shard-c"}
# ------------------------------------------------------------------------------
```

We could now choose between the following options:
1. **Making the gateway perform the operation to an another shard**: If we do this, why would we worry about having replicas if we are willing to wait until the failed node wakes up?
2. **Having 2 replicas per master**: This would increase the number of instances to run the system, thus, increasing the cost of running it, but it would effectively fix this.
#decision Based on what have been said, the option 2 is more suitable for our requirements.

## check:: Failover interval behavior

What if a client requests within the 3 seconds interval we told sentinels to wait until detecting a failover?

#todo