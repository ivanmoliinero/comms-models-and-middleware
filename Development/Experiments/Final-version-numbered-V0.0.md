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
sudo docker exec -i redis-master redis-cli -x EVAL "for i=2, 20000, 2 do redis.call('SET', 'seat-'..i, '1') end" 0
```

### Shard B (redis-master-b)
```bash
sudo docker exec -i redis-master redis-cli -x EVAL "for i=1, 19999, 2 do redis.call('SET', 'seat-'..i, '1') end" 0
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

```bash
sudo docker run --rm \
  --network host \
  -v $(pwd)/benchmark_numbered_60000.txt:/benchmark_data.txt:ro \
  -v $(pwd)/k6_benchmark.js:/k6_benchmark.js:ro \
  grafana/k6 run /k6_benchmark.js
  
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

## benchmark:: Redis loopback
A local `redis-benchmark` has been executed to see Redis real speed isolated from the system:

> [!warning] Important
> The following benchmark has been ran from another machine so it doesn't use the benchmarked resources themselves.

```bash
sudo docker exec redis-master redis-cli FLUSHALL
sudo docker exec redis-master redis-cli -x EVAL "for i=1, 10000, 1 do redis.call('SET', 'seat-'..i, '1') end" 0

sudo docker run --rm --network host redis:latest redis-benchmark -h 10.0.1.34 -p 6379 -c 100 -n 10000 -q --threads 8 --csv EVAL "local id = redis.call('INCR', KEYS[2]); local seat = 'seat-' .. id; local user = 'user-' .. id; if redis.call('SISMEMBER', KEYS[1], user) == 1 then return -1 end; if redis.call('DEL', seat) == 1 then redis.call('SADD', KEYS[1], user); return 1 end; return -2;" 2 purchased_tracking_ids bench_counter
```

![[final-versions/numbered/V0.0/benchmarks/rdis-master-a-localhost-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[final-versions/numbered/V0.0/benchmarks/rdis-master-a-localhost-benchmark.csv]]
```
In conclusion, Redis throughput is not the bottleneck in this case.