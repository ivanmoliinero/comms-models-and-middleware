---
final-version: V0.0
environment: AWS
tickets-mode: numbered
---
# Description

> [!important]
> This version is only prepared to handle **numbered tickets**.

This version is a modification of [[Development/Experiments/Final-version-unnumbered-V0.0|Final-version-unnumbered-V0.0]] given all the hard work has already been done there.

## Redis
### Data initialization

One of the modifications that must be done is the initialization of the shards data. We will have keys of the form `seat-<seat_id>`.
- If the key exists => the seat is available
- Else => the seat has been already purchased

### Logical sharding

Again, we do not need to make a real Redis cluster, it is enough with logical sharding. We will distribute the tickets among the shards the following way:
- **shard `i`** tickets: $\large{\{seatID\ |\ seatID \equiv i\ \mod\ numShards \}}$
- **shard `i+1`** tickets: $\large{\{seatID\ |\ seatID \equiv i+1\ \mod\ numShards \}}$
, and so on.

### New LUA functions

#### buy_ticket

```LUA
-- keys[1] = tracking_ids_set, keys[2] = seat_key
if redis.call('SISMEMBER', keys[1], args[1]) == 1 then
	return -1
end

-- DEL returns 1 if the key was deleted, 0 if it didn't exist
if redis.call('DEL', keys[2]) == 1 then 
	redis.call('SADD', keys[1], args[1])
	return 1 
end

return -2
```

#### rollback_ticket

```LUA
if redis.call('SREM', keys[1], args[1]) == 1 then 
	-- Recreate the seat ticket
	return redis.call('SET', keys[2], '1') 
end

return 0
```
## Gateway

We have now another parameter in each request indicating the `seat_id`, so gateways must be modified to handle this. Additionally, we must change the way we chose which shard to send the `buy_ticket` operation since we now know deterministically where the ticket will be found (as described in [[#Logical sharding]]) (if it is yet available).

# Deployment

## Boot the Redis replicas
Same as [[Development/Experiments/Final-version-unnumbered-V0.0#Boot the Redis replicas|Final-version-unnumbered-V0.0]].

## Redis LUA scripts update

Execute the following in each *redis-master*:
```bash
# First, clear the old data
sudo docker exec redis-master redis-cli FLUSHALL

# Load the new seat-based logic
cat << 'EOF' | sudo docker exec -i redis-master redis-cli -x FUNCTION LOAD REPLACE
#!lua name=ticket_sales
redis.register_function('buy_ticket', function(keys, args)
  -- keys[1] = tracking_ids_set, keys[2] = seat_key
  if redis.call('SISMEMBER', keys[1], args[1]) == 1 then return -1 end
  
  -- DEL returns 1 if the key was deleted, 0 if it didn't exist
  if redis.call('DEL', keys[2]) == 1 then 
    redis.call('SADD', keys[1], args[1])
    return 1 
  end
  return -2
end)

redis.register_function('rollback_ticket', function(keys, args)
  if redis.call('SREM', keys[1], args[1]) == 1 then 
    -- Recreate the seat ticket
    return redis.call('SET', keys[2], '1') 
  end
  return 0
end)
EOF
```

```LUA
redis.register_function('buy_ticket', function(keys, args)
  -- keys[1] = tracking_ids_set, keys[2] = seat_key
  if redis.call('SISMEMBER', keys[1], args[1]) == 1 then return -1 end
  
  -- DEL returns 1 if the key was deleted, 0 if it didn't exist
  if redis.call('DEL', keys[2]) == 1 then 
    redis.call('SADD', keys[1], args[1])
    return 1 
  end
  return -2
end

redis.register_function('rollback_ticket', function(keys, args)
  if redis.call('SREM', keys[1], args[1]) == 1 then 
    -- Recreate the seat ticket
    return redis.call('SET', keys[2], '1') 
  end
  return 0
end
```

## Populate Redis shards

### Shard A (redis-master-a)
```bash
sudo docker exec redis-master redis-cli -x EVAL "for i=2, 20000, 2 do redis.call('SET', 'seat-'..i, '1') end" 0
```

### Shard B (redis-master-b)
```bash
sudo docker exec redis-master redis-cli -x EVAL "for i=1, 19999, 2 do redis.call('SET', 'seat-'..i, '1') end" 0
```

## Deploy the Gateways

For each gateway:
```bash
# upload the nginx.conf file
scp -i SD-task1-key-pair.pem nginx.conf ubuntu@<gateway-public-ip>:.
ssh -i SD-task1-key-pair.pem ubuntu@<gateway-public-ip>

# inside SSH -------------------------------------------------------------------
sudo docker restart api-gateway
```

# Checks
## check:: Client request

```bash
# first purchase
curl -i "http://44.193.24.57/buy?ticket_id=manual-test-001&seat_id=1"
# output
{"status":"success","ip":"10.0.1.92","seat":"1","shard":"shard-b"}
# ------------------------------------------------------------------------------
# retry
curl -i "http://44.193.24.57/buy?ticket_id=manual-test-001&seat_id=1"
# output
{"error":"Ticket already purchased","processed_by":"shard-b"}
```

This is the expected behavior.

What if another client tries now to buy the same seat?
```bash
curl -i "http://44.193.24.57/buy?ticket_id=manual-test-002&seat_id=1"
# output
{"error":"Seat unavailable or sold out"}
```

Again, this is the expected behavior.

# Benchmarks
## benchmark:: Throughput

Locally, run the following from the path where [[final-versions/numbered/V0.0/benchmarks/k6_benchmark.js]] and [[benchmarks/benchmark_numbered_60000.txt|benchmark_numbered_60000.txt]] reside.

[benchmark:: Throughput] [vus:: 100] [workers: 2 per gateway]
```bash
sudo docker run --rm \
  --network host \
  -v $(pwd)/benchmark_numbered_60000.txt:/benchmark_data.txt:ro \
  -v $(pwd)/k6_benchmark.js:/k6_benchmark.js:ro \
  grafana/k6 run /k6_benchmark.js
```

```bash
  # output
    █ TOTAL RESULTS 

    checks_total.......: 103988 3744.745414/s
    checks_succeeded...: 25.00% 25997 out of 103988
    checks_failed......: 75.00% 77991 out of 103988

    ✗ Success (200 OK)
      ↳  76% — ✓ 20000 / ✗ 5997
    ✗ Duplicate ID (409 Conflict)
      ↳  0% — ✓ 0 / ✗ 25997
    ✗ Sold Out (410 Gone)
      ↳  23% — ✓ 5997 / ✗ 20000
    ✗ Gateway/DB Error (500+)
      ↳  0% — ✓ 0 / ✗ 25997

    HTTP
    http_req_duration..............: avg=105.57ms min=89.16ms med=103.99ms max=438.09ms p(90)=113.75ms p(95)=117.2ms 
      { expected_response:true }...: avg=107.17ms min=92.23ms med=105.82ms max=438.09ms p(90)=114.49ms p(95)=117.81ms
    http_req_failed................: 23.06% 5997 out of 25997
    http_reqs......................: 25997  936.186354/s

    EXECUTION
    iteration_duration.............: avg=106.32ms min=89.28ms med=104.1ms  max=438.23ms p(90)=113.88ms p(95)=117.34ms
    iterations.....................: 25997  936.186354/s
    vus............................: 100    min=100           max=100
    vus_max........................: 100    min=100           max=100

    NETWORK
    data_received..................: 6.2 MB 222 kB/s
    data_sent......................: 2.7 MB 98 kB/s


running (00m27.8s), 000/100 VUs, 25997 complete and 0 interrupted iterations
exact_requests ✓ [ 100% ] 100 VUs  00m27.8s/10m0s  25997/25997 shared iters

```

## benchmark:: Redis
A local `redis-benchmark` has been executed to see Redis real speed isolated from the system:

> [!warning] Important
> The following benchmark has been ran from another machine (*redis-master-b*) so it doesn't use the benchmarked resources themselves.

```bash
# initialize the database state
ssh -i SD-task1-key-pair.pem ubuntu@<redis-master-a>

# inside SSH -------------------------------------------------------------------
sudo docker exec redis-master redis-cli FLUSHALL
sudo docker exec redis-master redis-cli -x EVAL "for i=1, 10000, 1 do redis.call('SET', 'seat-'..i, '1') end" 0
```

```bash
ssh -i SD-task1-key-pair.pem ubuntu@<redis-master-b>

# inside SSH -------------------------------------------------------------------
sudo docker run --rm --network host redis:latest redis-benchmark -h 10.0.1.34 -p 6379 -c 100 -n 10000 -q --threads 8 --csv EVAL "local id = redis.call('INCR', KEYS[2]); local seat = 'seat-' .. id; local user = 'user-' .. id; if redis.call('SISMEMBER', KEYS[1], user) == 1 then return -1 end; if redis.call('DEL', seat) == 1 then redis.call('SADD', KEYS[1], user); return 1 end; return -2;" 2 purchased_tracking_ids bench_counter
```

![[final-versions/numbered/V0.0/benchmarks/redis-master-a-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[final-versions/numbered/V0.0/benchmarks/redis-master-a-benchmark.csv]]
```
In conclusion, Redis throughput is not the bottleneck in this case.

## Analysis of results

Looking at the [[#benchmark Throughput]] results, one could think that the system has an extreme bad performance compared to what Redis is capable of doing, so in conclusion you could think that there is an extreme unbalance in the system's architecture, but it is not.
In [[#benchmark Throughput]] we had been using `vus: 100`, which stands for ***virtual users***. The tool itself have been limiting the requests generation rate, so let's see what happens if we increase this number to really stress the system. A good number could be a bit less than $\large{4096 · 2 = 8192}$ since 4096 is the configured `worker_connections` parameter of the gateways' `nginx.conf` (we need a bit less because here are included all the gateway's connections, such as those from database pool). Though, those are lots of connections, so we are going to reduce it further to `vue: 3500` (you will see why next).

The whole output does not fit into an explanatory document, so just the most important sections of it will be showed.

The first 165 lines show how the system quickly responds to the **90 %** of the requests. From here on out, the system gets stucked.


[benchmark:: Throughput] [vus:: 3500] [workers: 2 per gateway]
```embed-bash
PATH: "vault://final-versions/numbered/V0.0/benchmarks/k6-result-vus-3500.txt"
LINES: "5-9, 158-165"
```

The *total results* show that 575 gateway errors have occurred.

```embed-bash
PATH: "vault://final-versions/numbered/V0.0/benchmarks/k6-result-vus-3500.txt"
LINES: "168-203"
```

> [!important]
> The reason why this happens is by the socket's queue overflowing. This can be proved by executing the following command on the *load balancer*:
> ```bash
> watch -d -n 1 'netstat -s | grep -E "overflowed|dropped"'
> ```
> This command will show how many times the queue overflows. If executed during the showed test (with 3500 vus), you will see the number increasing incredibly fast.

The system clearly exhausted, so let's execute another benchmark with `vus: 1000`.

[benchmark:: Throughput] [vus:: 1000] [workers: 2 per gateway]
```embed-bash
PATH: "vault://final-versions/numbered/V0.0/benchmarks/k6-full-result-vis-1000.txt"
```

Maybe still a bit exhausted:

[benchmark:: Throughput] [vus:: 800] [workers: 2 per gateway]
```embed-bash
PATH: "vault://final-versions/numbered/V0.0/benchmarks/k6-full-result-vus-800-4-workers.txt"
```

Finally, a good throughput of **4023 RPS**. But let's thoroughly analyse all the system with real time data to find the bottleneck.
#todo

## benchmark:: 1 Worker per Gateway

[benchmark:: Throughput] [vus:: 800] [workers: 1 per gateway]
```embed-bash
PATH: "vault://final-versions/numbered/V0.0/benchmarks/k6-full-result-vis-800-1-worker-per-gateway.txt"
```
