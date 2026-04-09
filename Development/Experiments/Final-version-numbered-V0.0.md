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

#todo