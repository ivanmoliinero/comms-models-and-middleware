---
experiment: RedisSharding+GatewayCluster+LoadBalancer
---
> [!warning]
> This experiment has been performed under lab conditions, so bear in mind that **resource limits** have been applied to every component if it.
# Other preparations
Same as [[Development/Experiments/Redis-OpenResty|Redis-OpenResty]].
# Redis
In this experiment we will focus on **sharding** rather than **replication**.

1. Create shards' data directories
```bash
mkdir shard-a-data shard-b-data
```

2. Spin up **shard A**
```bash
docker run -d \
  --name redis-shard-a \
  --network redis-test-net \
  -p 6379:6379 \
  -v $(pwd)/shard-a-data:/data \
  redis:latest redis-server --appendonly yes --appendfsync always
```

3. Spin up **shard B**
```bash
docker run -d \
  --name redis-shard-b \
  --network redis-test-net \
  -p 6380:6379 \
  -v $(pwd)/shard-b-data:/data \
  redis:latest redis-server --appendonly yes --appendfsync always
```

> [!important]
> The previous commands must be run from where we want the **data of the shards** to be contained.

> [!note]
> Note that the **published port** of the **shard B** it's a different one from the **shard A**.

3. Load the `buy_ticket` function to both shards as it was done in the step 2 of [[Development/Experiments/Redis-OpenResty#Redis|Redis-OpenResty#Redis]].
4. Set the initial state of each server. In this case, `tickets-counter` must have half the total tickets to sell in each one.

```redis-cli
# on each server
SET tickets-counter 10000
```

# Gateway
In this experiment we need to change the gateways' configuration to be able to implement the discussed solution [[Development/Experiments/Redis_replication-Gateway_cluster-Load_balancer#^4104cb|Redis_replication-Gateway_cluster-Load_balancer]]. Some details need to me mentioned about the new `nginx.conf`.

- The `resolver` config, as mentioned in the step 1 of [[Development/Experiments/Redis-OpenResty#Gateway|Redis-OpenResty#Gateway]].
```embed-shell
PATH: "vault://software-testing/redisSharding-gatewayCluster-loadBalancer/gateway/nginx.conf"
LINES: "6-7"
```

- The value of the module (2) depends on the number of shards.
```embed-shell
PATH: "vault://software-testing/redisSharding-gatewayCluster-loadBalancer/gateway/nginx.conf"
LINES: "30"
```

---
1. Spin up the unique gateway (we don't have a cluster in this experiment, therefore, neither a load balancer)
```bash
docker run -d \
  --name openresty-gateway \
  --network redis-test-net \
  --cpuset-cpus="1" \
  --memory="1g" \
  -p 8080:80 \
  -v $(pwd)/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro \
  openresty/openresty:latest
```

> [!important]
> The previous command must be run from the path that contains the [[software-testing/redisSharding-gatewayCluster-loadBalancer/gateway/nginx.conf]] file.

# Checks

We have to verify the following aspects:
- **BUY operation logic**
- **Uniform distribution** of the request since we no longer use a Round-Robin manner (it depends on the hash function)
- **Deterministic routing**

---

```bash
# client 1: first purchase
curl -i "http://localhost:8080/buy?ticket_id=test-uuid-001"
# output
{"processed_by":"Shard B","status":"success","ticket_number":9999}
# ------------------------------------------------------------------------------
# client 1: retry
curl -i "http://localhost:8080/buy?ticket_id=test-uuid-001"
# output
{"processed_by":"Shard B","status":"error","message":"Ticket already purchased with this ID"}
# ------------------------------------------------------------------------------
# client 2: first purchase
curl -i "http://localhost:8080/buy?ticket_id=test-uuid-002"
# output
{"processed_by":"Shard B","status":"success","ticket_number":9998}
# ------------------------------------------------------------------------------
# client 3: first purchase
curl -i "http://localhost:8080/buy?ticket_id=test-uuid-003"
# output
{"processed_by":"Shard B","status":"success","ticket_number":9997}
# ------------------------------------------------------------------------------
# client 4: first purchase
curl -i "http://localhost:8080/buy?ticket_id=test-uuid-004"
# output
{"processed_by":"Shard A","status":"success","ticket_number":9999}
# ------------------------------------------------------------------------------
# client 4: retry
curl -i "http://localhost:8080/buy?ticket_id=test-uuid-004"
# output
{"processed_by":"Shard A","status":"error","message":"Ticket already purchased with this ID"}
# ------------------------------------------------------------------------------
# client 5: first purchase
curl -i "http://localhost:8080/buy?ticket_id=test-uuid-005"
# output
{"processed_by":"Shard A","status":"success","ticket_number":9998}
# ------------------------------------------------------------------------------
# client 6: first purchase
curl -i "http://localhost:8080/buy?ticket_id=test-uuid-006"
# output
{"processed_by":"Shard A","status":"success","ticket_number":9997}
# ------------------------------------------------------------------------------
```

> [!important]
> This set of commands has validated the **logic of the BUY operation** (except for the *sold-out* cases), **deterministic routing**, since retries have been routed to the same *first-purchase* shard, and also **uniform distribution** of the requests.

> [!note]
> Some irrelevant data of the outputs has been skipped, such as
> ```plain
> HTTP/1.1 200 OK
> Server: openresty/1.29.2.3
> Date: Tue, 07 Apr 2026 14:40:04 GMT
> Content-Type: application/json
> Transfer-Encoding: chunked
> Connection: keep-alive
> ```

To check the *sold-out* cases, we can force the system to effectively run out of tickets, but first, uniquely in one server.
We will empty the `redis-shard-a` of tickets since the client 7 (which will perform the next request) will be redirected to it first.

```bash
docker exec -it redis-shard-a redis-cli
127.0.0.1:6379> SET tickets-counter 0
```

```bash
# client 7: first purchase
curl -i "http://localhost:8080/buy?ticket_id=test-uuid-007"
# output
{"processed_by":"Shard B","status":"success","ticket_number":9999}
```

It successfully have been redirected to an another shard. To check the *retry execution path* when the first shard is sold out we can perform the following.

```bash
# client 7: retry
curl -i "http://localhost:8080/buy?ticket_id=test-uuid-007"
# output
{"processed_by":"Shard B","status":"error","message":"Ticket already purchased with this ID"}
```