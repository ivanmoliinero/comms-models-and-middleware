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

The LUA script [[final-versions/numbered/V0.0/benchmarks/file_benchmark.lua]] parses the [[benchmarks/benchmark_numbered_60000.txt|benchmark_numbered_60000.txt]] file to benchmark its requests.

```embed-bash
PATH: "vault://final-versions/numbered/V0.0/benchmarks/file_benchmark.lua"
```

```bash
sudo docker run --rm \
  --network host \
  -v $(pwd)/benchmark_numbered_60000.txt:/benchmark_data.txt:ro \
  -v $(pwd)/file_benchmark.lua:/benchmark.lua:ro \
  williamyeh/wrk \
  -t1 -c100 -d60s -s /benchmark.lua http://44.193.24.57
  
# output
Running 1m test @ http://44.193.24.57
  1 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   128.40ms   48.91ms 752.35ms   91.70%
    Req/Sec   801.28    231.92     1.30k    79.62%
  25913 requests in 1.00m, 5.86MB read
  Non-2xx or 3xx responses: 5996
Requests/sec:    431.88
Transfer/sec:    100.00KB
```

A local `redis-benchmark` has been executed to see Redis real speed isolated from the system:

```bash
sudo docker run --rm --network host redis:latest redis-benchmark -h 127.0.0.1 -p 6379 -c 100 -n 60000 -q --threads 8 -r 20000 --csv fcall buy_ticket_bench 2 purchased_tracking_ids seat-__rand_int__ client-__rand_int__
"test","rps","avg_latency_ms","min_latency_ms","p50_latency_ms","p95_latency_ms","p99_latency_ms","max_latency_ms"
"fcall buy_ticket_bench 2 purchased_tracking_ids seat-__rand_int__ client-__rand_int__","13289.04","6.695","1.672","5.719","9.343","11.279","24.479"
```

![[final-versions/numbered/V0.0/benchmarks/rdis-master-a-localhost-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[final-versions/numbered/V0.0/benchmarks/rdis-master-a-localhost-benchmark.csv]]
```

